/** Users & Roles admin screen: users, roles and the permission matrix. */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";
import { CheckRow, ConfirmDialog, MultiSelect, toggleIn, useToast } from "@/components/erp/extras";
import { Shell } from "@/components/erp/shell";
import { Tabs } from "@/components/erp/tabs";
import { ActionButton, DataTable, DesktopOnly, EmptyState, Field, FilterSelect, Forbidden, InlineError, MobileOnly, MobileRecordCard, MobileRecordRow, Modal, Note, PageHeader, Pagination, Pill, SearchInput, SelectInput, TextArea, TextInput } from "@/components/erp/ui";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { useApiQuery, useAsyncAction, useDebounced, type ListResponse } from "@/lib/hooks";

interface UserRow {
  id: string;
  email: string;
  displayName: string;
  status: string;
  roles: string[];
  managerId?: string | null;
  managerName?: string | null;
  mfaEnabled?: boolean;
}
interface RoleRow {
  id: string;
  name: string;
  description?: string | null;
  permissions: string[];
  userCount: number;
  isSystem?: boolean;
}
interface PermissionRow {
  permission: string;
  resource: string;
  description: string;
}
interface Site {
  id: string;
  name: string;
}
interface UserDetail {
  managerId?: string | null;
  roleAssignments?: { roleId: string; warehouseIds?: string[]; factoryIds?: string[] }[];
}

const STATUS_OPTIONS = [
  { label: "Active", value: "active" },
  { label: "Suspended", value: "suspended" },
  { label: "Invited", value: "invited" },
];

/** Fetches all roles page-by-page up to MAX_PAGES (limit 200 = API max). */
export async function fetchAllRoles(api: <T>(method: string, path: string, options?: any) => Promise<T>): Promise<RoleRow[]> {
  const rows: RoleRow[] = [];
  const MAX_PAGES = 50;
  for (let page = 1; page <= MAX_PAGES; page += 1) {
    const resp = await api<ListResponse<RoleRow>>("GET", "/api/v1/roles", { params: { limit: 200, page } });
    if (!resp.data?.length) break;
    rows.push(...resp.data);
    if (page >= (resp.meta?.pages ?? 1)) break;
  }
  return rows;
}

/** Roles are a small bounded reference list used in full by several UIs, so every page is fetched (limit 200 = the API's max). */
function useAllRoles(enabled: boolean) {
  const { api } = useAuth();
  return useQuery<RoleRow[]>({
    queryKey: ["/api/v1/roles#all"],
    enabled,
    retry: false,
    queryFn: () => fetchAllRoles(api),
  });
}

function SiteAccessFields({ warehouses, factories, warehouseIds, factoryIds, onWarehouse, onFactory }: { warehouses: Site[]; factories: Site[]; warehouseIds: string[]; factoryIds: string[]; onWarehouse: (id: string) => void; onFactory: (id: string) => void }) {
  return (
    <div className="flex w-full flex-col items-start gap-1">
      <p className="text-sm font-bold">Site access (optional)</p>
      <p className="text-xs text-[var(--muted-foreground)]">Restrict this user to specific warehouses/factories — leave none selected for access to all sites.</p>
      <div className="flex w-full gap-2">
        <MultiSelect items={warehouses} selected={warehouseIds} onToggle={onWarehouse} getId={(w) => w.id} getLabel={(w) => w.name} placeholder="All warehouses" width="16rem" />
        <MultiSelect items={factories} selected={factoryIds} onToggle={onFactory} getId={(f) => f.id} getLabel={(f) => f.name} placeholder="All factories" width="16rem" />
      </div>
    </div>
  );
}

function RolePicker({ roles, selected, onToggle }: { roles: RoleRow[]; selected: string[]; onToggle: (id: string) => void }) {
  return (
    <MultiSelect items={roles} selected={selected} onToggle={onToggle} getId={(r) => r.id} getLabel={(r) => r.name} placeholder="Select roles…" countLabel={(n) => `${n} role(s) selected`} searchable searchPlaceholder="Search roles…" />
  );
}

// ---- users tab ---------------------------------------------------------------------------

function UsersTab({ roles, warehouses, factories }: { roles: RoleRow[]; warehouses: Site[]; factories: Site[] }) {
  const { api, can } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounced(search, 250);
  const [statusFilter, setStatusFilter] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [pageError, setPageError] = useState("");

  const usersQuery = useApiQuery<ListResponse<UserRow>>(
    "/api/v1/users",
    {
      q: debouncedSearch.trim() || undefined,
      status: statusFilter || undefined,
      roleId: roleFilter || undefined,
      page,
      limit: 25,
    },
    { enabled: can("user:read") },
  );
  const users = usersQuery.data?.data ?? [];

  // Active users query for manager dropdown selection (unpaginated up to 200)
  const managersQuery = useApiQuery<ListResponse<UserRow>>(
    "/api/v1/users",
    { status: "active", limit: 200 },
    { enabled: can("user:read") },
  );
  const managerUsers = managersQuery.data?.data ?? users;

  const handleSearch = (v: string) => {
    setSearch(v);
    setPage(1);
  };
  const handleStatusFilter = (v: string) => {
    setStatusFilter(v);
    setPage(1);
  };
  const handleRoleFilter = (v: string) => {
    setRoleFilter(v);
    setPage(1);
  };

  const resendInvite = async (id: string, email: string) => {
    setPageError("");
    try {
      await api("POST", `/api/v1/users/${id}/resend-invite`);
      toast.success(`Invitation resent to ${email}`);
    } catch (exc) {
      setPageError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  // Anyone active can be a manager (never the person themselves - the API also refuses loops).
  const managerOptions = (selfId?: string) => [
    { value: "", label: "No manager" },
    ...managerUsers.filter((u) => u.status === "active" && u.id !== selfId).map((u) => ({ value: u.id, label: `${u.displayName} (${u.email})` })),
  ];

  const refresh = () => qc.invalidateQueries({ queryKey: ["/api/v1/users"] });

  // ---- invite
  const [inviteOpen, setInviteOpen] = useState(false);
  const invite = useAsyncAction();
  const [inviteRoles, setInviteRoles] = useState<string[]>([]);
  const [inviteWh, setInviteWh] = useState<string[]>([]);
  const [inviteFac, setInviteFac] = useState<string[]>([]);
  const [inviteManager, setInviteManager] = useState("");
  const openInvite = () => {
    setInviteRoles([]);
    setInviteWh([]);
    setInviteFac([]);
    setInviteManager("");
    invite.setError("");
    setInviteOpen(true);
  };
  const createUser = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const password = String(f.get("password") ?? "");
    const body: Record<string, unknown> = {
      email: String(f.get("email") ?? ""),
      displayName: String(f.get("displayName") ?? ""),
      businessUnit: String(f.get("businessUnit") ?? "") || null,
      managerId: inviteManager || null,
      status: password ? "active" : "invited",
      roles: inviteRoles.map((roleId) => ({ roleId, scopes: [], warehouseIds: inviteWh, factoryIds: inviteFac })),
    };
    if (password) body.password = password;
    const ok = await invite.run(async () => {
      await api("POST", "/api/v1/users", { json: body });
      return true;
    });
    if (ok) {
      setInviteOpen(false);
      await refresh();
    }
  };

  const [manageId, setManageId] = useState("");
  const [manageRoles, setManageRoles] = useState<string[]>([]);
  const [manageWh, setManageWh] = useState<string[]>([]);
  const [manageFac, setManageFac] = useState<string[]>([]);
  const [manageManager, setManageManager] = useState("");
  const [userSessions, setUserSessions] = useState<Array<{ id: string; device: string; ip: string | null; issuedAt: string | null }>>([]);
  const [openingManageId, setOpeningManageId] = useState<string | null>(null);
  const openingManageRef = useRef<string | null>(null);
  const manage = useAsyncAction();
  const openManage = async (id: string) => {
    if (openingManageRef.current) return;
    openingManageRef.current = id;
    setOpeningManageId(id);
    setPageError("");
    try {
      const detail = await api<UserDetail>("GET", `/api/v1/users/${id}`);
      if (openingManageRef.current !== id) return;
      const assignments = detail.roleAssignments ?? [];
      setManageId(id);
      setManageManager(detail.managerId ?? "");
      setManageRoles(assignments.map((a) => a.roleId));
      // Existing assignments may still carry per-role scope from before site
      // access became a single per-user setting - show their union.
      setManageWh([...new Set(assignments.flatMap((a) => a.warehouseIds ?? []))].sort());
      setManageFac([...new Set(assignments.flatMap((a) => a.factoryIds ?? []))].sort());
      try {
        const sessRes = await api<{ sessions: Array<{ id: string; device: string; ip: string | null; issuedAt: string | null }> }>("GET", `/api/v1/users/${id}/sessions`);
        if (openingManageRef.current === id) {
          setUserSessions(sessRes.sessions ?? []);
        }
      } catch {
        if (openingManageRef.current === id) {
          setUserSessions([]);
        }
      }
      manage.setError("");
    } catch (exc) {
      setPageError(exc instanceof ApiError ? exc.detail : exc instanceof Error ? exc.message : String(exc));
    } finally {
      if (openingManageRef.current === id) {
        openingManageRef.current = null;
        setOpeningManageId(null);
      }
    }
  };
  const revokeUserSessions = async () => {
    try {
      await api("DELETE", `/api/v1/users/${manageId}/sessions`);
      setUserSessions([]);
      toast.success("All sessions for this user have been terminated");
    } catch (exc) {
      manage.setError(exc instanceof Error ? exc.message : String(exc));
    }
  };
  const saveManage = async () => {
    const ok = await manage.run(async () => {
      await api("PATCH", `/api/v1/users/${manageId}/roles`, { json: { roles: manageRoles.map((roleId) => ({ roleId, scopes: [], warehouseIds: manageWh, factoryIds: manageFac })), mode: "replace" } });
      try {
        await api("PATCH", `/api/v1/users/${manageId}`, { json: { managerId: manageManager || null } });
      } catch (exc) {
        const detail = exc instanceof ApiError ? exc.detail : exc instanceof Error ? exc.message : String(exc);
        throw new Error(`Roles updated, but assigning manager failed: ${detail}. Please retry manager selection.`);
      }
      return true;
    });
    if (ok) {
      setManageId("");
      await refresh();
    }
  };

  const setStatus = async (id: string, status: string) => {
    setPageError("");
    try {
      await api("PATCH", `/api/v1/users/${id}`, { json: { status } });
      await refresh();
    } catch (exc) {
      setPageError(exc instanceof Error ? exc.message : String(exc));
    }
  };
  const statusButton = (u: UserRow, cls?: string) =>
    u.status === "suspended" ? (
      <ActionButton size="sm" className={cls} onClick={() => setStatus(u.id, "active")}>Activate</ActionButton>
    ) : (
      <ActionButton size="sm" className={cls} onClick={() => setStatus(u.id, "suspended")}>Suspend</ActionButton>
    );
  const mfa = (u: UserRow) => (u.mfaEnabled ? <Pill tone="success">on</Pill> : <Pill>off</Pill>);

  return (
    <div className="flex w-full flex-col items-start gap-4">
      <InlineError message={pageError || usersQuery.error?.message} />
      <div className="flex w-full flex-wrap md:flex-nowrap items-center gap-2">
        <div className="w-64">
          <SearchInput value={search} onChange={handleSearch} placeholder="Search by name or email…" />
        </div>
        <FilterSelect value={statusFilter} onChange={handleStatusFilter} options={STATUS_OPTIONS} label="All statuses" />
        <FilterSelect value={roleFilter} onChange={handleRoleFilter} options={roles.map((r) => ({ label: r.name, value: r.id }))} label="All roles" />
        <div className="flex-1" />
        <ActionButton onClick={openInvite}>Invite user</ActionButton>
      </div>
      {users.length === 0 ? (
        <EmptyState title="No users found" hint="Try adjusting your search query, status, or role filter." />
      ) : (
        <>
          <DesktopOnly className="w-full">
            <DataTable columns={["Name", "Email", "Status", "Roles", "Reports to", "MFA", ""]} minWidth={640} fit>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.displayName}</td>
                  <td>{u.email}</td>
                  <td><Pill>{u.status}</Pill></td>
                  <td>{u.roles.join(", ")}</td>
                  <td>{u.managerName || "—"}</td>
                  <td>{mfa(u)}</td>
                  <td>
                    <div className="flex gap-2">
                      <ActionButton size="sm" loading={openingManageId === u.id} onClick={() => openManage(u.id)}>Manage roles</ActionButton>
                      {u.status === "invited" && (
                        <ActionButton size="sm" tone="ghost" onClick={() => resendInvite(u.id, u.email)}>Resend invite</ActionButton>
                      )}
                      {statusButton(u)}
                    </div>
                  </td>
                </tr>
              ))}
            </DataTable>
          </DesktopOnly>
          <MobileOnly className="w-full">
            {users.map((u) => (
              <MobileRecordCard
                key={u.id}
                actions={
                  <>
                    <ActionButton size="sm" className="w-full justify-center" loading={openingManageId === u.id} onClick={() => openManage(u.id)}>Manage roles</ActionButton>
                    {u.status === "invited" && (
                      <ActionButton size="sm" tone="ghost" className="w-full justify-center" onClick={() => resendInvite(u.id, u.email)}>Resend invite</ActionButton>
                    )}
                    {statusButton(u, "w-full justify-center")}
                  </>
                }
              >
                <MobileRecordRow label="Name" value={u.displayName} />
                <MobileRecordRow label="Email" value={u.email} />
                <MobileRecordRow label="Status" value={<Pill>{u.status}</Pill>} />
                <MobileRecordRow label="Roles" value={u.roles.join(", ")} />
                <MobileRecordRow label="Reports to" value={u.managerName || "—"} />
                <MobileRecordRow label="MFA" value={mfa(u)} />
              </MobileRecordCard>
            ))}
          </MobileOnly>
        </>
      )}
      <div className="w-full">
        <Pagination meta={usersQuery.data?.meta} onPage={setPage} />
      </div>

      <Modal open={inviteOpen} onClose={() => setInviteOpen(false)} title="Invite user">
        <form onSubmit={createUser} className="flex flex-col gap-3">
          <InlineError message={invite.error} />
          <TextInput name="email" type="email" placeholder="Email" required />
          <TextInput name="displayName" placeholder="Display name" required />
          <TextInput name="businessUnit" placeholder="Business unit (optional)" />
          <Field label="Reports to" hint="Approves their purchase requisitions">
            <SelectInput value={inviteManager} onChange={(e) => setInviteManager(e.target.value)} options={managerOptions()} />
          </Field>
          <TextInput name="password" type="password" placeholder="Password (leave blank to invite)" />
          <p className="text-sm font-bold">Roles</p>
          <RolePicker roles={roles} selected={inviteRoles} onToggle={(id) => setInviteRoles(toggleIn(inviteRoles, id))} />
          <SiteAccessFields warehouses={warehouses} factories={factories} warehouseIds={inviteWh} factoryIds={inviteFac} onWarehouse={(id) => setInviteWh(toggleIn(inviteWh, id))} onFactory={(id) => setInviteFac(toggleIn(inviteFac, id))} />
          <div className="flex justify-end gap-2">
            <ActionButton tone="ghost" onClick={() => setInviteOpen(false)}>Cancel</ActionButton>
            <ActionButton type="submit" loading={invite.busy}>Create user</ActionButton>
          </div>
        </form>
      </Modal>

      <Modal open={manageId !== ""} onClose={() => setManageId("")} title="Manage roles">
        <div className="flex flex-col gap-3">
          <InlineError message={manage.error} />
          <Field label="Reports to" hint="Approves their purchase requisitions">
            <SelectInput value={manageManager} onChange={(e) => setManageManager(e.target.value)} options={managerOptions(manageId)} />
          </Field>
          <RolePicker roles={roles} selected={manageRoles} onToggle={(id) => setManageRoles(toggleIn(manageRoles, id))} />
          <SiteAccessFields warehouses={warehouses} factories={factories} warehouseIds={manageWh} factoryIds={manageFac} onWarehouse={(id) => setManageWh(toggleIn(manageWh, id))} onFactory={(id) => setManageFac(toggleIn(manageFac, id))} />
          <div className="pt-2 border-t border-[var(--border)]">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-[var(--foreground)]">Active Sessions</p>
                <p className="text-xs text-[var(--muted-foreground)]">
                  {userSessions.length} active device session{userSessions.length === 1 ? "" : "s"}
                </p>
              </div>
              {userSessions.length > 0 && (
                <ActionButton size="sm" tone="ghost" onClick={revokeUserSessions}>
                  Terminate all sessions
                </ActionButton>
              )}
            </div>
          </div>
          <div className="mt-2 flex justify-end gap-2">
            <ActionButton tone="ghost" onClick={() => setManageId("")}>Cancel</ActionButton>
            <ActionButton onClick={saveManage} loading={manage.busy}>Save</ActionButton>
          </div>
        </div>
      </Modal>
    </div>
  );
}

// ---- roles tab ------------------------------------------------------------------------------

function PermissionChecklist({ permissions, selected, onToggle, disabled }: { permissions: PermissionRow[]; selected: string[]; onToggle: (p: string) => void; disabled?: boolean }) {
  return (
    <div className="check-list w-full" style={{ height: "16rem", maxHeight: "16rem" }}>
      {permissions.map((p) => (
        <CheckRow key={p.permission} label={`${p.permission} — ${p.description}`} checked={selected.includes(p.permission)} disabled={disabled} onChange={() => onToggle(p.permission)} />
      ))}
    </div>
  );
}

function RolesTab({ roles, permissions }: { roles: RoleRow[]; permissions: PermissionRow[] }) {
  const { api } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const refresh = () => qc.invalidateQueries({ queryKey: ["/api/v1/roles#all"] });

  const [createOpen, setCreateOpen] = useState(false);
  const [createPerms, setCreatePerms] = useState<string[]>([]);
  const create = useAsyncAction();
  const submitCreate = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const ok = await create.run(async () => {
      await api("POST", "/api/v1/roles", { json: { name: String(f.get("name") ?? ""), description: String(f.get("description") ?? ""), permissions: createPerms } });
      return true;
    });
    if (ok) {
      setCreateOpen(false);
      await refresh();
    }
  };

  const [editId, setEditId] = useState("");
  const [edit, setEdit] = useState({ isSystem: false, name: "", description: "", permissions: [] as string[] });
  const editAction = useAsyncAction();
  const openEdit = (r: RoleRow) => {
    setEditId(r.id);
    setEdit({ isSystem: !!r.isSystem, name: r.name, description: r.description ?? "", permissions: [...r.permissions] });
    editAction.setError("");
  };
  const submitEdit = async (e: FormEvent) => {
    e.preventDefault();
    const body: Record<string, unknown> = { description: edit.description };
    if (!edit.isSystem) {
      body.name = edit.name;
      body.permissions = edit.permissions;
    }
    const ok = await editAction.run(async () => {
      await api("PATCH", `/api/v1/roles/${editId}`, { json: body });
      return true;
    });
    if (ok) {
      setEditId("");
      await refresh();
    }
  };

  const [deleteId, setDeleteId] = useState("");
  const del = useAsyncAction();
  const confirmDelete = async () => {
    const role = roles.find((r) => r.id === deleteId);
    const ok = await del.run(async () => {
      await api("DELETE", `/api/v1/roles/${deleteId}`);
      return true;
    });
    if (ok) {
      setDeleteId("");
      await refresh();
      toast.success(`"${role?.name ?? "Role"}" was deleted.`);
    }
  };

  const actions = (r: RoleRow, cls?: string) => (
    <>
      <ActionButton size="sm" className={cls} onClick={() => openEdit(r)}>Edit</ActionButton>
      <ActionButton size="sm" tone="danger" className={cls} disabled={!!r.isSystem} onClick={() => { del.setError(""); setDeleteId(r.id); }}>Delete</ActionButton>
    </>
  );
  const kind = (r: RoleRow) => (r.isSystem ? <Pill>system</Pill> : <span>custom</span>);

  return (
    <div className="flex w-full flex-col items-start gap-4">
      <div className="flex w-full items-center">
        <h3 className="rx-heading-4">Roles</h3>
        <div className="flex-1" />
        <ActionButton onClick={() => { setCreatePerms([]); create.setError(""); setCreateOpen(true); }}>Create role</ActionButton>
      </div>
      <DesktopOnly className="w-full">
        <DataTable columns={["Name", "Description", "Permissions", "Users", "System", ""]} minWidth={640} fit>
          {roles.map((r) => (
            <tr key={r.id}>
              <td>{r.name}</td>
              <td>{r.description}</td>
              <td>{r.permissions.length} permissions</td>
              <td>{r.userCount}</td>
              <td>{kind(r)}</td>
              <td><div className="flex gap-2">{actions(r)}</div></td>
            </tr>
          ))}
        </DataTable>
      </DesktopOnly>
      <MobileOnly className="w-full">
        {roles.map((r) => (
          <MobileRecordCard key={r.id} actions={actions(r, "w-full justify-center")}>
            <MobileRecordRow label="Name" value={r.name} />
            <MobileRecordRow label="Description" value={r.description} />
            <MobileRecordRow label="Permissions" value={`${r.permissions.length} permissions`} />
            <MobileRecordRow label="Users" value={r.userCount} />
            <MobileRecordRow label="System" value={kind(r)} />
          </MobileRecordCard>
        ))}
      </MobileOnly>

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Create role">
        <form onSubmit={submitCreate} className="flex flex-col gap-3">
          <InlineError message={create.error} />
          <TextInput name="name" placeholder="Role name" required />
          <TextArea name="description" placeholder="Description" />
          <p className="text-sm font-bold">Permissions</p>
          <PermissionChecklist permissions={permissions} selected={createPerms} onToggle={(p) => setCreatePerms(toggleIn(createPerms, p))} />
          <div className="flex justify-end gap-2">
            <ActionButton tone="ghost" onClick={() => setCreateOpen(false)}>Cancel</ActionButton>
            <ActionButton type="submit" loading={create.busy}>Create role</ActionButton>
          </div>
        </form>
      </Modal>

      <Modal open={editId !== ""} onClose={() => setEditId("")} title="Edit role">
        <form onSubmit={submitEdit} className="flex flex-col gap-3">
          {edit.isSystem && <Note>System roles: only the description can be changed.</Note>}
          <InlineError message={editAction.error} />
          <TextInput value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} placeholder="Role name" disabled={edit.isSystem} />
          <TextArea value={edit.description} onChange={(e) => setEdit({ ...edit, description: e.target.value })} placeholder="Description" />
          <p className="text-sm font-bold">Permissions</p>
          <PermissionChecklist permissions={permissions} selected={edit.permissions} disabled={edit.isSystem} onToggle={(p) => setEdit({ ...edit, permissions: toggleIn(edit.permissions, p) })} />
          <div className="flex justify-end gap-2">
            <ActionButton tone="ghost" onClick={() => setEditId("")}>Cancel</ActionButton>
            <ActionButton type="submit" loading={editAction.busy}>Save changes</ActionButton>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={deleteId !== ""}
        title="Delete role"
        description="This permanently deletes the role. Users still holding it must be unassigned first. This can't be undone."
        error={del.error}
        onCancel={() => setDeleteId("")}
        onConfirm={confirmDelete}
      />
    </div>
  );
}

// ---- permission matrix ------------------------------------------------------------------------

function MatrixTab({ roles, permissions }: { roles: RoleRow[]; permissions: PermissionRow[] }) {
  const resources = [...new Set(permissions.map((p) => p.resource))];
  return (
    <div className="flex w-full flex-col items-start gap-4">
      <h3 className="rx-heading-4">Permission matrix</h3>
      <div className="matrix-scroll-box" style={{ maxHeight: "calc(100vh - 16rem)", overflowY: "auto", overflowX: "scroll", width: "100%" }}>
        <table className="data-table data-table-fit" style={{ minWidth: 1800 }}>
          <thead>
            <tr>
              <th>Role</th>
              {resources.map((r) => (
                <th key={r}>{r}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {roles.map((role) => {
              const hasAll = role.permissions.includes("*");
              return (
                <tr key={role.id}>
                  <td>{role.name}</td>
                  {resources.map((res) => {
                    const has = hasAll || role.permissions.includes(`${res}:*`) || role.permissions.some((p) => p.startsWith(`${res}:`));
                    return <td key={res}>{has ? <Pill tone="success">✓</Pill> : <span>–</span>}</td>;
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function UsersPage() {
  const { can } = useAuth();
  const canRoles = can("role:read");
  const canUsers = can("user:read");
  const rolesQuery = useAllRoles(canRoles);
  const permsQuery = useApiQuery<{ data: PermissionRow[] }>("/api/v1/permissions", undefined, { enabled: canRoles });
  // Populate the role-assignment site-scope picker - gated on user:read (this
  // page's own nav permission); the backend's list endpoints accept it.
  const warehouses = useApiQuery<ListResponse<Site>>("/api/v1/warehouses", { limit: 100 }, { enabled: canUsers });
  const factories = useApiQuery<ListResponse<Site>>("/api/v1/factories", { limit: 100 }, { enabled: canUsers });
  const roles = rolesQuery.data ?? [];
  const permissions = permsQuery.data?.data ?? [];

  return (
    <Shell fullWidth>
      {canUsers || canRoles ? (
        <div className="flex w-full flex-col gap-4">
          <PageHeader fit eyebrow="Foundation" title="Users & Roles" />
          <InlineError message={rolesQuery.error?.message} />
          <Tabs
            tabs={[
              { value: "users", label: "Users", content: <UsersTab roles={roles} warehouses={warehouses.data?.data ?? []} factories={factories.data?.data ?? []} /> },
              { value: "roles", label: "Roles", content: <RolesTab roles={roles} permissions={permissions} /> },
              { value: "matrix", label: "Permission matrix", content: <MatrixTab roles={roles} permissions={permissions} /> },
            ]}
          />
        </div>
      ) : (
        <Forbidden permission="user:read" />
      )}
    </Shell>
  );
}
