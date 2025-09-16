// frontend/src/lib/api.ts
export type InvoiceListItem = {
  id: string
  filename?: string | null
  intestatario?: string | null
  invoice_number?: string | null
  data_emissione?: string | null
  totale?: number | null
}

export type InvoiceListResponse = {
  items: InvoiceListItem[]
  total: number
  limit: number
  offset: number
}

const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ||
  "http://localhost:8000"

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => "")
    throw new Error(`HTTP ${res.status} ${res.statusText} - ${text}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  baseUrl: API_BASE,
  getInvoices: (params?: { limit?: number; offset?: number }) => {
    const q = new URLSearchParams()
    if (params?.limit) q.set("limit", String(params.limit))
    if (params?.offset) q.set("offset", String(params.offset))
    const qs = q.toString() ? `?${q.toString()}` : ""
    return http<InvoiceListResponse>(`/api/v1/invoices${qs}`)
  },
  getInvoiceDownloadUrl: async (id: string, expires_in = 900) => {
    const data = await http<{ url: string; expires_in: number }>(
      `/api/v1/invoices/${id}/download?expires_in=${expires_in}`
    )
    return data.url
  },
}
