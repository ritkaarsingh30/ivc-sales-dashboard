import { createContext, useContext, useState, useMemo, useCallback, useEffect } from 'react'

const FilterContext = createContext(null)

export function FilterProvider({ availableMonths = [], children }) {
  // null = "all months" — avoids having to keep the set in sync with availableMonths
  const [selectedMonths, setSelectedMonths] = useState(null)

  // Reset to "all" whenever the available set changes (e.g. new month loaded)
  useEffect(() => {
    setSelectedMonths(null)
  }, [availableMonths.join(',')])

  const activeMonths = useMemo(() => {
    if (!selectedMonths) return availableMonths
    return availableMonths.filter(m => selectedMonths.has(m))
  }, [selectedMonths, availableMonths])

  const isFiltered = selectedMonths !== null

  const isMonthSelected = useCallback((month) => {
    if (!selectedMonths) return true
    return selectedMonths.has(month)
  }, [selectedMonths])

  const toggleMonth = useCallback((month) => {
    setSelectedMonths(prev => {
      const base = prev ? new Set(prev) : new Set(availableMonths)
      if (base.has(month)) {
        base.delete(month)
        // Nothing left → reset to all
        if (base.size === 0) return null
      } else {
        base.add(month)
        // All re-selected → back to "all"
        if (base.size === availableMonths.length) return null
      }
      return base
    })
  }, [availableMonths])

  const setPreset = useCallback((months) => {
    const available = months.filter(m => availableMonths.includes(m))
    if (!available.length || available.length === availableMonths.length) {
      setSelectedMonths(null)
    } else {
      setSelectedMonths(new Set(available))
    }
  }, [availableMonths])

  const clearFilter = useCallback(() => setSelectedMonths(null), [])

  return (
    <FilterContext.Provider value={{
      availableMonths,
      activeMonths,
      isFiltered,
      isMonthSelected,
      toggleMonth,
      setPreset,
      clearFilter,
    }}>
      {children}
    </FilterContext.Provider>
  )
}

export function useFilter() {
  const ctx = useContext(FilterContext)
  if (!ctx) throw new Error('useFilter must be used inside FilterProvider')
  return ctx
}
