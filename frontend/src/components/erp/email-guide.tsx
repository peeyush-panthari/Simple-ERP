/**
 * Email Config > "Setup guide": where to find every value the Email Config cards ask for, step by step, for Gmail /
 * Google Workspace, Microsoft 365 and any other SMTP provider, plus what each field means and what common errors say.
 */
import type { ReactNode } from "react";

import { Tabs } from "@/components/erp/tabs";
import { ActionButton, Modal, Note } from "@/components/erp/ui";

export type GuideTab = "gmail" | "microsoft" | "other" | "fields" | "errors";

function A({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="rx-link">
      {children}
    </a>
  );
}

function Steps({ children }: { children: ReactNode }) {
  return <ol className="flex list-none flex-col gap-3 p-0 text-sm">{children}</ol>;
}

function Step({ n, title, children }: { n: number; title: string; children?: ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--primary)] text-xs font-semibold text-[var(--primary-foreground)]">{n}</span>
      <div className="min-w-0">
        <p className="font-semibold">{title}</p>
        {children ? <div className="mt-1 flex flex-col gap-1 text-[var(--muted-foreground)]">{children}</div> : null}
      </div>
    </li>
  );
}

function Values({ rows }: { rows: [string, string][] }) {
  return (
    <div className="overflow-hidden rounded-md border border-[var(--border)] text-sm">
      {rows.map(([k, v]) => (
        <div key={k} className="flex flex-wrap gap-x-3 border-b border-[var(--border)] px-3 py-1.5 last:border-b-0">
          <span className="w-40 shrink-0 text-[var(--muted-foreground)]">{k}</span>
          <span className="min-w-0 font-medium">{v}</span>
        </div>
      ))}
    </div>
  );
}

function Gmail() {
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-[var(--muted-foreground)]">
        Works for a normal Gmail address and for a company address hosted on Google Workspace. Gmail does not accept your everyday password from other
        apps - you create a separate 16-character <b>App password</b> for Simple ERP.
      </p>
      <Steps>
        <Step n={1} title="Sign in to the Google account that will send the emails">
          <p>Use the exact mailbox the emails should come from, for example <b>orders@yourcompany.com</b>. Use a separate mailbox per kind of email if you want different senders.</p>
        </Step>
        <Step n={2} title="Turn on 2-Step Verification">
          <p>
            Open <A href="https://myaccount.google.com/signinoptions/two-step-verification">Google Account -&gt; Security -&gt; 2-Step Verification</A>, press <b>Get started</b>{" "}
            and confirm with your phone. App passwords only exist once this is on.
          </p>
        </Step>
        <Step n={3} title="Create an App password">
          <p>
            Open <A href="https://myaccount.google.com/apppasswords">myaccount.google.com/apppasswords</A>, type a name such as <b>Simple ERP</b> and press <b>Create</b>.
            Google shows a 16-character password (like <b>abcd efgh ijkl mnop</b>). Copy it now - Google shows it only once. The spaces do not matter.
          </p>
          <p>If that page says the setting is not available: 2-Step Verification is still off, the account uses Advanced Protection, or (Workspace) your administrator has blocked app passwords.</p>
        </Step>
        <Step n={4} title="Fill in the card in Email Config">
          <p>Press <b>Set up</b> on the kind of email, choose the preset <b>Gmail / Google Workspace</b>, then enter:</p>
          <Values
            rows={[
              ["SMTP server", "smtp.gmail.com"],
              ["Port / security", "587 with STARTTLS   (or 465 with SSL/TLS)"],
              ["Username", "the full Gmail address, e.g. orders@yourcompany.com"],
              ["Password", "the 16-character app password from step 3"],
              ["Sender email", "the same address as the username"],
              ["Sender name", "what recipients see, e.g. Yourcompany Purchasing"],
            ]}
          />
          <p>Tick <b>Use its own mailbox</b> and press <b>Save</b>.</p>
        </Step>
        <Step n={5} title="Send a test email">
          <p>Type your own address under <b>Send a test email to</b> and press the button. Check the inbox (and Spam). A green &quot;passed&quot; means real emails will work.</p>
        </Step>
      </Steps>
      <Note>
        Gmail always sends as the signed-in address, so keep <b>Sender email</b> equal to <b>Username</b>. To send as a different address, first add it in Gmail under Settings -&gt;
        Accounts -&gt; &quot;Send mail as&quot; and verify it. Limits: about 500 recipients a day for a personal Gmail, about 2,000 for Workspace - fine for orders and invoices.
      </Note>
    </div>
  );
}

function Microsoft() {
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-[var(--muted-foreground)]">For a company mailbox on Microsoft 365 / Outlook.com. Microsoft has been switching off password sign-in for SMTP in many organisations, so ask your IT admin if it fails.</p>
      <Steps>
        <Step n={1} title="Ask your Microsoft 365 admin to allow SMTP for the mailbox">
          <p>
            In the <A href="https://admin.microsoft.com/">Microsoft 365 admin center</A>: Users -&gt; Active users -&gt; pick the mailbox -&gt; <b>Mail</b> -&gt; <b>Manage email apps</b> -&gt; tick{" "}
            <b>Authenticated SMTP</b> -&gt; Save. Changes can take up to 30 minutes.
          </p>
        </Step>
        <Step n={2} title="Get the password to use">
          <p>
            If the account has multi-factor sign-in, create an app password at <A href="https://mysignins.microsoft.com/security-info">mysignins.microsoft.com/security-info</A> (Add sign-in method -&gt; App password).
            Without multi-factor, the mailbox password is used.
          </p>
        </Step>
        <Step n={3} title="Fill in the card in Email Config">
          <Values
            rows={[
              ["SMTP server", "smtp.office365.com"],
              ["Port / security", "587 with STARTTLS"],
              ["Username", "the full mailbox address"],
              ["Password", "the password or app password from step 2"],
              ["Sender email", "the same mailbox address (or an alias the mailbox may send as)"],
            ]}
          />
        </Step>
        <Step n={4} title="Save and send a test email">
          <p>If it says <b>535 5.7.139 authentication unsuccessful</b>, SMTP sign-in is blocked for your organisation: use an email relay service instead (see the &quot;Other provider&quot; tab).</p>
        </Step>
      </Steps>
    </div>
  );
}

function Other() {
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-[var(--muted-foreground)]">
        A company mail server, a web-hosting mailbox, or an email delivery service. You need six things - your IT team or the provider&apos;s &quot;SMTP settings&quot; help page has them.
      </p>
      <Steps>
        <Step n={1} title="Find out these values">
          <Values
            rows={[
              ["SMTP server", "e.g. mail.yourcompany.com"],
              ["Port", "587 (most common), 465, or 25"],
              ["Security", "STARTTLS on 587, SSL/TLS on 465"],
              ["Username", "often the full email address"],
              ["Password", "the mailbox password or an SMTP/API password"],
              ["Allowed sender", "the address the account is allowed to send as"],
            ]}
          />
        </Step>
        <Step n={2} title="Enter them on the card and test">
          <p>Fill the card, tick <b>Use its own mailbox</b>, press <b>Save</b>, then <b>Send test email</b>. The error message from the server appears on the card if it refuses.</p>
        </Step>
      </Steps>
      <div>
        <p className="mb-1 text-sm font-semibold">Common providers</p>
        <div className="overflow-x-auto">
          <table className="data-table data-table-fit">
            <thead>
              <tr>
                <th>Provider</th>
                <th>SMTP server</th>
                <th>Port / security</th>
                <th>Username</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Zoho Mail", "smtp.zoho.com (smtp.zoho.in in India)", "465 SSL/TLS or 587 STARTTLS", "full address (app password)"],
                ["Yahoo Mail", "smtp.mail.yahoo.com", "465 SSL/TLS", "full address (app password)"],
                ["Amazon SES", "email-smtp.<region>.amazonaws.com", "587 STARTTLS", "SES SMTP user name"],
                ["SendGrid", "smtp.sendgrid.net", "587 STARTTLS", "the word apikey (password = API key)"],
                ["Mailgun", "smtp.mailgun.org", "587 STARTTLS", "postmaster@your-domain"],
                ["Postmark", "smtp.postmarkapp.com", "587 STARTTLS", "server API token"],
              ].map((r) => (
                <tr key={r[0]}>
                  {r.map((c, i) => (
                    <td key={i}>{c}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <Note>For high volume or to send from a dedicated domain, an email delivery service is the sturdier choice. Add SPF and DKIM records for your domain (the service shows you which) so mail reaches the inbox.</Note>
    </div>
  );
}

function Fields() {
  const rows: [string, string][] = [
    ["Send these emails", "Off = this kind of email is not sent at all (the document shows \"failed\" with a note)."],
    ["Use its own mailbox", "On = this kind leaves from the mailbox on the card. Off = it goes through the server's default mail settings."],
    ["SMTP server", "The mail server's address, e.g. smtp.gmail.com. The mail provider tells you this."],
    ["Port", "The door on that server. 587 is the standard for sending; 465 is the older encrypted one."],
    ["Connection security", "STARTTLS goes with port 587, SSL/TLS with port 465. Choose None only for a trusted server inside your own network."],
    ["Username", "The login for the mailbox - usually the full email address."],
    ["Password", "For Gmail and many others an app password, not the everyday one. Stored encrypted; never shown again. Leave blank to keep the saved one."],
    ["Sender name / Sender email", "What recipients see in \"From\". Most providers require the sender email to be the login address or one of its verified aliases."],
    ["Reply-to", "Where replies go if you want them somewhere else, e.g. help@yourcompany.com. Optional."],
    ["Always Cc / Always Bcc", "Addresses that get a copy of every email of this kind (Bcc = hidden). Separate several with commas."],
  ];
  return (
    <div className="flex flex-col gap-3">
      <Values rows={rows} />
      <p className="text-sm text-[var(--muted-foreground)]">
        <b>Reuse another kind&apos;s mailbox:</b> if purchase orders and invoices use the same account, set it up once, then on the other card pick it under <b>Or reuse another kind&apos;s mailbox</b> -
        the login is copied without retyping the password.
      </p>
    </div>
  );
}

function Errors() {
  const rows: [string, string][] = [
    ["535 ... Username and Password not accepted", "Wrong password. For Gmail use the 16-character app password (2-Step Verification must be on), not the normal one. Re-enter it and save."],
    ["530 ... Must issue a STARTTLS command first", "Connection security is set to None on port 587. Choose STARTTLS."],
    ["SSL: WRONG_VERSION_NUMBER  /  unexpected EOF", "Port and security do not match: 587 needs STARTTLS, 465 needs SSL/TLS."],
    ["Connection timed out / refused", "Wrong server name or port, or your network blocks outgoing mail ports (587/465). Ask IT to allow them, or try the other port."],
    ["553 / 550 sender not allowed, or \"not authorized to send as\"", "The Sender email is not the login address or a verified alias. Make it the same as the Username."],
    ["Test passed but the email lands in Spam", "Ask whoever manages your domain to add SPF and DKIM records for the sending server, and a DMARC record."],
    ["This kind of email is switched off in Email Config", "The \"Send these emails\" box on that card is unticked. Tick it and save."],
  ];
  return <Values rows={rows} />;
}

export function EmailSetupGuide({ open, onClose, tab, onTab }: { open: boolean; onClose: () => void; tab: GuideTab; onTab: (t: GuideTab) => void }) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Email setup guide"
      description="Where to find each value the cards ask for."
      wide
      maxWidth="46rem"
      footer={<ActionButton tone="ghost" onClick={onClose}>Close</ActionButton>}
    >
      <Tabs
        value={tab}
        onValueChange={(v) => onTab(v as GuideTab)}
        tabs={[
          { value: "gmail", label: "Gmail / Workspace", content: <Gmail /> },
          { value: "microsoft", label: "Microsoft 365", content: <Microsoft /> },
          { value: "other", label: "Other provider", content: <Other /> },
          { value: "fields", label: "What each field means", content: <Fields /> },
          { value: "errors", label: "If it fails", content: <Errors /> },
        ]}
      />
    </Modal>
  );
}
