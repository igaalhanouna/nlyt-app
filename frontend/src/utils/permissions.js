/**
 * Centralized Role-Permission Mapping — NLYT Frontend
 * Must mirror backend/utils/permissions.py exactly.
 */

const ROLE_PERMISSIONS = {
  admin: ['*'],
  arbitrator: ['admin:arbitration'],
  payer: ['admin:payouts', 'admin:stale-payouts'],
  accreditor: ['admin:associations'],
  user: [],
};

export const ALL_ROLES = Object.keys(ROLE_PERMISSIONS);

export const ROLE_LABELS = {
  admin: 'Admin',
  arbitrator: 'Arbitre',
  payer: 'Payeur',
  accreditor: 'Accrediteur',
  user: 'Utilisateur',
};

export const ROLE_COLORS = {
  admin: 'bg-amber-100 text-amber-700 border-amber-200',
  arbitrator: 'bg-purple-100 text-purple-700 border-purple-200',
  payer: 'bg-blue-100 text-blue-700 border-blue-200',
  accreditor: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  user: 'bg-slate-100 text-slate-600 border-slate-200',
};

export function hasPermission(role, permission) {
  const perms = ROLE_PERMISSIONS[role] || [];
  return perms.includes('*') || perms.includes(permission);
}

export function hasAnyAdminPermission(role) {
  const perms = ROLE_PERMISSIONS[role] || [];
  return perms.includes('*') || perms.some(p => p.startsWith('admin:'));
}
