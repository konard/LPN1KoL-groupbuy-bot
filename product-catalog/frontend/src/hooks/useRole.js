export function useRole(user) {
  const role = user?.role || ''
  return {
    isAdmin: role === 'admin',
    isAdvanced: role === 'advanced_user' || role === 'admin',
    canDelete: role === 'advanced_user' || role === 'admin',
    canManageCategories: role === 'advanced_user' || role === 'admin',
    canManageUsers: role === 'admin',
    canSeeSpecialNote: role === 'advanced_user' || role === 'admin',
  }
}
