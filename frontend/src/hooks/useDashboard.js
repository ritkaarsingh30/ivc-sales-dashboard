import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const useOverview = () => useQuery({
  queryKey: ['overview'],
  queryFn: () => api.get('/overview').then(r => r.data)
})

export const useMonth = (month) => useQuery({
  queryKey: ['month', month],
  queryFn: () => api.get(`/months/${month}`).then(r => r.data),
  enabled: !!month
})

export const useProducts = () => useQuery({
  queryKey: ['products'],
  queryFn: () => api.get('/products').then(r => r.data)
})

export const useDelegates = () => useQuery({
  queryKey: ['delegates'],
  queryFn: () => api.get('/delegates').then(r => r.data)
})

export const useExpenses = () => useQuery({
  queryKey: ['expenses'],
  queryFn: () => api.get('/expenses').then(r => r.data)
})

export const useInsights = () => useQuery({
  queryKey: ['insights'],
  queryFn: () => api.get('/insights').then(r => r.data)
})

export const useRefreshInsights = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post('/insights/refresh').then(r => r.data),
    onSuccess: (data) => {
      qc.setQueryData(['insights'], data)
    }
  })
}

export const useRefreshData = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post('/data/refresh').then(r => r.data),
    onSuccess: () => {
      // Invalidate ALL cached queries so every tab refetches fresh data
      qc.invalidateQueries()
    }
  })
}
