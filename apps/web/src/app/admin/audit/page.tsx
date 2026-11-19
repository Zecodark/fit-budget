"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, ApiClientError } from "@/lib/api";
import { ErrorBanner } from "@/components/StatusWidgets";

export default function AdminAuditPage() {
  const [items, setItems] = useState<any[]>([]);
  const [entityType, setEntityType] = useState("");
  const [error, setError] = useState<{ msg: string; reqId?: string } | null>(null);

  const loadAudit = useCallback(async () => {
    try {
      const q = entityType ? `?entity_type=${encodeURIComponent(entityType)}` : "";
      const res = await apiFetch<{ items: any[] }>(`/admin/audit${q}`);
      setItems(res.items || []);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  }, [entityType]);

  useEffect(() => {
    loadAudit();
  }, [loadAudit]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Admin — Log Audit Perubahan</h1>
          <p className="text-sm text-slate-600">
            Catatan seluruh aksi mutasi katalog pangan, harga, dan gerakan latihan oleh admin.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs font-semibold">
          <Link href="/admin/foods" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5">
            Katalog Pangan
          </Link>
          <Link href="/admin/prices" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5">
            Harga Pangan
          </Link>
          <Link href="/admin/exercises" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5">
            Katalog Latihan
          </Link>
        </div>
      </div>

      {error ? <ErrorBanner message={error.msg} requestId={error.reqId} /> : null}

      <div className="flex items-center gap-3">
        <label htmlFor="entity-filter" className="text-xs font-semibold text-slate-700">
          Filter Entitas:
        </label>
        <select
          id="entity-filter"
          value={entityType}
          onChange={(e) => setEntityType(e.target.value)}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs"
        >
          <option value="">Semua Entitas</option>
          <option value="food">food</option>
          <option value="food_price">food_price</option>
          <option value="exercise">exercise</option>
        </select>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm overflow-x-auto">
        {items.length === 0 ? (
          <p className="text-sm text-slate-500">Belum ada entri audit.</p>
        ) : (
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-slate-600">
                <th className="py-2">Waktu</th>
                <th className="py-2">Aksi</th>
                <th className="py-2">Entitas</th>
                <th className="py-2">Alasan</th>
                <th className="py-2">Sesudah (Ringkas)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((it) => (
                <tr key={it.id}>
                  <td className="py-2 whitespace-nowrap">{it.created_at}</td>
                  <td className="py-2 font-semibold">{it.action}</td>
                  <td className="py-2">{it.entity_type}</td>
                  <td className="py-2">{it.reason}</td>
                  <td className="py-2 font-mono text-[11px] max-w-md truncate">
                    {JSON.stringify(it.after_json)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

