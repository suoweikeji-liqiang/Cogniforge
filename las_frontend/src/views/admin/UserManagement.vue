<template>
  <div class="user-management">
    <h1>{{ t('admin.users') }}</h1>
    <table class="users-table">
      <thead>
        <tr>
          <th>{{ t('users.username') }}</th>
          <th>{{ t('users.email') }}</th>
          <th>{{ t('users.role') }}</th>
          <th>{{ t('users.status') }}</th>
          <th>{{ t('users.createdAt') }}</th>
          <th>{{ t('common.actions') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="user in users" :key="user.id">
          <td>{{ user.username }}</td>
          <td>{{ user.email }}</td>
          <td>
            <select v-model="user.role" @change="updateUser(user)">
              <option value="admin">{{ t('users.admin') }}</option>
              <option value="user">{{ t('users.user') }}</option>
            </select>
          </td>
          <td>{{ user.is_active ? t('users.active') : t('users.inactive') }}</td>
          <td>{{ new Date(user.created_at).toLocaleDateString() }}</td>
          <td>
            <button @click="showResetPassword(user)">{{ t('users.resetPassword') }}</button>
            <button @click="deleteUser(user)">{{ t('common.delete') }}</button>
          </td>
        </tr>
      </tbody>
    </table>
    
    <div v-if="showModal" class="modal">
      <div class="modal-content">
        <h3>{{ t('users.resetPassword') }}</h3>
        <input v-model="newPassword" type="password" :placeholder="t('users.newPassword')" />
        <button @click="resetPassword">{{ t('common.save') }}</button>
        <button @click="showModal = false">{{ t('common.cancel') }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/api'

const { t } = useI18n()
const users = ref([])
const showModal = ref(false)
const selectedUser = ref(null)
const newPassword = ref('')

const loadUsers = async () => {
  const response = await api.get('/admin/users')
  users.value = response.data
}

const updateUser = async (user) => {
  await api.put(`/admin/users/${user.id}`, {
    role: user.role,
    is_active: user.is_active
  })
}

const showResetPassword = (user) => {
  selectedUser.value = user
  showModal.value = true
}

const resetPassword = async () => {
  await api.put(`/admin/users/${selectedUser.value.id}`, {
    password: newPassword.value
  })
  showModal.value = false
  newPassword.value = ''
}

const deleteUser = async (user) => {
  if (confirm(t('users.confirmDelete'))) {
    await api.delete(`/admin/users/${user.id}`)
    loadUsers()
  }
}

onMounted(loadUsers)
</script>

<style scoped>
.user-management h1 {
  color: var(--text);
  margin-bottom: 1.5rem;
}
.users-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--bg-card);
  border-radius: 12px;
  overflow: hidden;
}
.users-table th, .users-table td {
  padding: 12px;
  border-bottom: 1px solid var(--border);
  text-align: left;
  color: var(--text);
}
.users-table th {
  background: var(--bg-dark);
  color: var(--text-muted);
  font-weight: 500;
  font-size: 0.875rem;
}
.users-table select {
  background: var(--bg-dark);
  color: var(--text);
  border: 1px solid var(--border);
  padding: 6px 10px;
  border-radius: 6px;
}
.users-table button {
  background: var(--bg-dark);
  color: var(--text-muted);
  border: 1px solid var(--border);
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  margin-right: 8px;
  font-size: 0.75rem;
}
.users-table button:hover {
  background: var(--primary);
  color: var(--bg-dark);
  border-color: var(--primary);
}
.modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal-content {
  background: var(--bg-card);
  border: 1px solid var(--border);
  padding: 24px;
  border-radius: 12px;
  min-width: 320px;
}
.modal-content h3 {
  color: var(--text);
  margin-bottom: 1rem;
}
.modal-content input {
  width: 100%;
  padding: 10px;
  margin-bottom: 12px;
  background: var(--bg-dark);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
}
.modal-content button {
  background: var(--primary);
  color: var(--bg-dark);
  border: none;
  padding: 10px 16px;
  border-radius: 6px;
  cursor: pointer;
  margin-right: 8px;
}
.modal-content button:last-child {
  background: var(--bg-dark);
  color: var(--text-muted);
  border: 1px solid var(--border);
}
</style>
