"""Foundation > Email Config: the API, the password never leaking, the per-purpose rules, and that a message really
leaves through the tenant's own mailbox (a small SMTP server stands in for it)."""

import socketserver
import threading
import uuid

import pytest

from app.core.db import SessionLocal
from app.models.email_config import EmailConfig
from app.services import email_config_repo, notification_repo, notification_transport


class _SmtpHandler(socketserver.StreamRequestHandler):
    def handle(self):
        srv = self.server
        w = lambda line: self.wfile.write((line + "\r\n").encode())
        w("220 stub ESMTP")
        msg = None
        while True:
            line = self.rfile.readline().decode(errors="replace").rstrip("\r\n")
            if not line:
                return
            cmd = line.upper()
            if cmd.startswith("EHLO"):
                w("250-stub"); w("250 AUTH PLAIN LOGIN")
            elif cmd.startswith("AUTH"):
                srv.auth.append(line)
                if srv.reject_auth:
                    w("535 5.7.8 Username and Password not accepted")
                else:
                    w("235 2.7.0 Accepted")
            elif cmd.startswith("MAIL FROM"):
                msg = {"from": line[10:].strip("<> "), "rcpt": [], "data": ""}
                w("250 OK")
            elif cmd.startswith("RCPT TO"):
                msg["rcpt"].append(line[8:].strip("<> "))
                w("250 OK")
            elif cmd == "DATA":
                w("354 go")
                body = []
                while True:
                    l = self.rfile.readline().decode(errors="replace")
                    if l in (".\r\n", ".\n"):
                        break
                    body.append(l)
                msg["data"] = "".join(body)
                srv.messages.append(msg)
                w("250 queued")
            elif cmd == "QUIT":
                w("221 bye")
                return
            else:
                w("250 OK")


@pytest.fixture
def smtp_stub():
    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    srv = Server(("127.0.0.1", 0), _SmtpHandler)
    srv.messages, srv.auth, srv.reject_auth = [], [], False
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


@pytest.fixture
def admin(client, fresh_admin, default_tenant_id, app):
    with app.app_context():
        EmailConfig.query.filter_by(tenant_id=default_tenant_id).delete()
        SessionLocal.commit()
    resp = client.post("/api/v1/auth/login", json={"email": fresh_admin["email"], "password": fresh_admin["password"]})
    yield {"Authorization": f"Bearer {resp.get_json()['accessToken']}"}
    with app.app_context():
        EmailConfig.query.filter_by(tenant_id=default_tenant_id).delete()
        SessionLocal.commit()


PO, INV, RFQ = "purchase-order.issued", "invoice.issued", "logistics.rfq"


def _body(port, **over):
    body = {"sendEnabled": True, "useOwnMailbox": True, "smtpHost": "127.0.0.1", "smtpPort": port, "security": "none", "smtpUser": "acct@example.test", "smtpPassword": "s3cret-app-pw",
            "fromName": "Acme Accounts", "fromEmail": "acct@example.test", "replyTo": "help@example.test", "cc": [], "bcc": []}
    body.update(over)
    return body


def _put(client, admin, key, body):
    return client.put(f"/api/v1/email-config/{key}", json=body, headers=admin)


def _get(client, admin, key=None):
    cfg = client.get("/api/v1/email-config", headers=admin).get_json()
    return cfg if key is None else next(p for p in cfg["purposes"] if p["key"] == key)


def test_defaults_before_anything_is_saved(client, admin):
    cfg = _get(client, admin)
    assert [p["key"] for p in cfg["purposes"]] == ["purchase-order.issued", "purchase-rfq.issued", "logistics.rfq", "invoice.issued", "logistics.pre-dispatch", "user.invitation"]
    assert all(p["sendEnabled"] and not p["useOwnMailbox"] and not p["configured"] and not p["passwordSet"] for p in cfg["purposes"])
    assert {p["key"] for p in cfg["presets"]} == {"gmail", "outlook"}


def test_each_kind_is_saved_separately(client, admin, smtp_stub):
    port = smtp_stub.server_address[1]
    assert _put(client, admin, PO, _body(port, fromEmail="orders@example.test", smtpUser="orders@example.test")).status_code == 200
    assert _put(client, admin, INV, _body(port, fromEmail="billing@example.test", smtpUser="billing@example.test", cc=["ar@example.test"])).status_code == 200
    po, inv, rfq = _get(client, admin, PO), _get(client, admin, INV), _get(client, admin, RFQ)
    assert (po["fromEmail"], inv["fromEmail"], inv["cc"]) == ("orders@example.test", "billing@example.test", ["ar@example.test"])
    assert po["cc"] == [] and not rfq["configured"]  # saving invoices touched nothing else
    # editing one leaves the other alone
    _put(client, admin, PO, _body(port, fromEmail="orders2@example.test", smtpPassword=None))
    assert _get(client, admin, INV)["fromEmail"] == "billing@example.test" and _get(client, admin, PO)["fromEmail"] == "orders2@example.test"


def test_password_is_write_only_and_sealed_at_rest(client, admin, app, default_tenant_id, smtp_stub):
    port = smtp_stub.server_address[1]
    saved = _put(client, admin, INV, _body(port))
    assert saved.status_code == 200, saved.get_json()
    assert "s3cret-app-pw" not in str(saved.get_json()) and saved.get_json()["passwordSet"] is True
    assert "s3cret-app-pw" not in str(client.get("/api/v1/email-config", headers=admin).get_json())
    with app.app_context():
        row = EmailConfig.query.filter_by(tenant_id=default_tenant_id, purpose_key=INV).one()
        assert row.smtp_password_sealed.startswith("v1.") and "s3cret" not in row.smtp_password_sealed
    _put(client, admin, INV, _body(port, smtpPassword=None))  # omitted -> kept
    assert _get(client, admin, INV)["passwordSet"] is True
    _put(client, admin, INV, _body(port, smtpPassword=""))  # "" -> removed
    assert _get(client, admin, INV)["passwordSet"] is False


def test_validation(client, admin):
    put = lambda key=INV, **o: _put(client, admin, key, _body(587, **o))
    assert put(smtpHost="").status_code == 422  # own mailbox needs a host
    assert put(fromEmail="not-an-address").status_code == 422
    assert put(security="tls").status_code == 422
    assert put(smtpPort=0).status_code == 400  # schema-level
    assert put(cc=["bad address"]).status_code == 422
    assert put(key="nope.kind").status_code == 404


def test_needs_the_permission(client, admin):
    from tests.test_cross_module_lookup_permissions import _create_role, _create_user_with_role  # noqa: F401

    assert client.get("/api/v1/email-config").status_code == 401
    ids = {"users": [], "roles": []}
    admin_token = admin["Authorization"].split(" ")[1]
    try:
        reader = _create_user_with_role(client, admin_token, ids, _create_role(client, admin_token, ids, ["email_config:read"])["id"])[1]
        nothing = _create_user_with_role(client, admin_token, ids, _create_role(client, admin_token, ids, ["po:read"])["id"])[1]
        h = lambda t: {"Authorization": f"Bearer {t}"}
        assert client.get("/api/v1/email-config", headers=h(reader)).status_code == 200
        assert client.put(f"/api/v1/email-config/{INV}", json=_body(587), headers=h(reader)).status_code == 403
        assert client.post(f"/api/v1/email-config/{INV}/test", json={"to": "a@example.test"}, headers=h(reader)).status_code == 403
        assert client.delete(f"/api/v1/email-config/{INV}", headers=h(reader)).status_code == 403
        assert client.get("/api/v1/email-config", headers=h(nothing)).status_code == 403
    finally:
        from tests.flaskcompat import db as _db
        from app.models.password_history import PasswordHistory
        from app.models.role import Role
        from app.models.role_permission import RolePermission
        from app.models.session import Session
        from app.models.user import User
        from app.models.user_role import UserRole

        u = [uuid.UUID(i) for i in ids["users"]]
        r = [uuid.UUID(i) for i in ids["roles"]]
        UserRole.query.filter(UserRole.user_id.in_(u) | UserRole.role_id.in_(r)).delete(synchronize_session=False)
        Session.query.filter(Session.user_id.in_(u)).delete(synchronize_session=False)
        PasswordHistory.query.filter(PasswordHistory.user_id.in_(u)).delete(synchronize_session=False)
        User.query.filter(User.id.in_(u)).delete(synchronize_session=False)
        RolePermission.query.filter(RolePermission.role_id.in_(r)).delete(synchronize_session=False)
        Role.query.filter(Role.id.in_(r)).delete(synchronize_session=False)
        _db.session.commit()


def test_test_email_uses_that_kinds_mailbox_and_records_the_result(client, admin, smtp_stub):
    port = smtp_stub.server_address[1]
    url = f"/api/v1/email-config/{INV}/test"
    assert client.post(url, json={"to": "someone@example.test"}, headers=admin).status_code == 422  # nothing saved yet
    _put(client, admin, INV, _body(port))
    ok = client.post(url, json={"to": "someone@example.test"}, headers=admin).get_json()
    assert ok["ok"] is True and ok["purpose"]["lastTest"]["ok"] is True
    msg = smtp_stub.messages[-1]
    assert msg["rcpt"] == ["someone@example.test"] and msg["from"] == "acct@example.test"
    assert "Acme Accounts" in msg["data"] and "Reply-To: help@example.test" in msg["data"] and "Customer invoices" in msg["data"]
    assert smtp_stub.auth
    assert _get(client, admin, PO)["lastTest"]["at"] is None  # another kind's record is untouched
    smtp_stub.reject_auth = True
    bad = client.post(url, json={"to": "someone@example.test"}, headers=admin).get_json()
    assert bad["ok"] is False and "535" in bad["error"] and bad["purpose"]["lastTest"]["ok"] is False


def test_purchase_orders_and_invoices_leave_through_different_mailboxes(client, admin, smtp_stub, default_tenant_id, app):
    """The point of the module: PO mail from one address/server, invoices from another, RFQs blocked, the rest default."""
    port_po = smtp_stub.server_address[1]

    class Server2(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    other = Server2(("127.0.0.1", 0), _SmtpHandler)
    other.messages, other.auth, other.reject_auth = [], [], False
    threading.Thread(target=other.serve_forever, daemon=True).start()
    try:
        _put(client, admin, PO, _body(port_po, fromEmail="orders@example.test", smtpUser="orders@example.test", fromName="Acme Purchasing"))
        _put(client, admin, INV, _body(other.server_address[1], fromEmail="billing@example.test", smtpUser="billing@example.test", fromName="Acme Billing", cc=["accounts@example.test"], bcc=["audit@example.test"], replyTo="ar@example.test"))
        _put(client, admin, RFQ, _body(port_po, sendEnabled=False, useOwnMailbox=False, smtpHost="", fromEmail=""))
        with app.app_context():
            r1 = notification_repo.send_notification(default_tenant_id, template="invoice.issued", to=["cust@example.test"], data={"number": "INV-1", "total": "100", "dueDate": "2026-10-01", "currency": "INR"})
            assert r1["status"] == "sent", r1
            assert len(other.messages) == 1 and len(smtp_stub.messages) == 0  # the invoice used the billing server only
            m = other.messages[0]
            assert m["from"] == "billing@example.test" and set(m["rcpt"]) == {"cust@example.test", "accounts@example.test", "audit@example.test"}
            head = m["data"].split("\r\n\r\n")[0]
            assert "Acme Billing" in head and "Cc: accounts@example.test" in head and "Reply-To: ar@example.test" in head and "audit@example.test" not in head

            r2 = notification_repo.send_notification(default_tenant_id, template="purchase-order.issued", to=["vendor@example.test"], data={"number": "PO-1", "vendor": {"name": "V"}})
            assert r2["status"] == "sent", r2
            assert len(smtp_stub.messages) == 1 and len(other.messages) == 1
            assert smtp_stub.messages[0]["from"] == "orders@example.test" and "Acme Purchasing" in smtp_stub.messages[0]["data"]

            from app.core.errors import ProblemError
            with pytest.raises(ProblemError) as exc:
                notification_repo.send_notification(default_tenant_id, template="logistics.rfq", to=["carrier@example.test"], data={"rfqNumber": "R1", "lane": "A-B"})
            assert exc.value.code == "EMAIL_PURPOSE_DISABLED"
    finally:
        other.shutdown()
        other.server_close()


def test_copy_reset_and_environment_fallback(client, admin, smtp_stub, default_tenant_id, app):
    port = smtp_stub.server_address[1]
    _put(client, admin, PO, _body(port))
    copied = client.post(f"/api/v1/email-config/{INV}/copy-from", json={"sourceKey": PO}, headers=admin).get_json()
    assert copied["useOwnMailbox"] and copied["passwordSet"] and copied["fromEmail"] == "acct@example.test"
    assert client.post(f"/api/v1/email-config/{INV}/copy-from", json={"sourceKey": RFQ}, headers=admin).status_code == 422  # RFQ has nothing saved
    with app.app_context():
        assert email_config_repo.resolve(default_tenant_id, INV).source == "tenant"
        assert email_config_repo.resolve(default_tenant_id, RFQ).source == "environment"
        assert email_config_repo.resolve(default_tenant_id, "user.invitation").source == "environment"
    reset = client.delete(f"/api/v1/email-config/{INV}", headers=admin).get_json()
    assert reset["configured"] is False and not reset["useOwnMailbox"]
    assert _get(client, admin, PO)["configured"] is True  # the source kept its own
    with app.app_context():
        assert email_config_repo.resolve(default_tenant_id, INV).source == "environment"
    # own mailbox switched off = default server, but the kind's Cc/off switch still apply
    _put(client, admin, PO, _body(port, useOwnMailbox=False, cc=["x@example.test"]))
    with app.app_context():
        assert email_config_repo.resolve(default_tenant_id, PO).source == "environment"
        assert email_config_repo.purpose_rules(default_tenant_id, PO)["cc"] == ["x@example.test"]
