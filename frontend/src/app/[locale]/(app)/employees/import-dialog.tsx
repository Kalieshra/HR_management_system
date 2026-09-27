'use client';

import { useMutation } from '@tanstack/react-query';
import { Download, Loader2, Upload } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useRef, useState } from 'react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useInvalidateCompany } from '@/hooks/use-api';
import { api, apiUrl } from '@/lib/api';

interface PreviewRow {
  row: number;
  code: string;
  name_ar: string;
  branch_name: string;
  base_salary: string;
  action: 'create' | 'update';
}

interface PreviewError {
  row: number;
  code: string;
  name: string;
  errors: string[];
}

interface PreviewResponse {
  total: number;
  valid: PreviewRow[];
  errors: PreviewError[];
  summary: { create: number; update: number; failed: number };
}

/** Upload → preview with per-row errors → commit. Nothing is saved until the
 *  user confirms, which matters when a bad sheet could rewrite every salary. */
export function ImportDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslations('employees.import');
  const tc = useTranslations('common');
  const invalidate = useInvalidateCompany();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);

  const upload = useMutation({
    mutationFn: (chosen: File) => {
      const data = new FormData();
      data.append('file', chosen);
      return api.upload<PreviewResponse>('/api/v1/employees/import/', data);
    },
    onSuccess: setPreview,
    onError: () => toast.error(tc('genericError')),
  });

  const commit = useMutation({
    mutationFn: (chosen: File) => {
      const data = new FormData();
      data.append('file', chosen);
      return api.upload<{ created: number; updated: number }>(
        '/api/v1/employees/import/commit/',
        data,
      );
    },
    onSuccess: (result) => {
      toast.success(t('done', { created: result.created, updated: result.updated }));
      invalidate();
      reset();
      onOpenChange(false);
    },
    onError: () => toast.error(tc('genericError')),
  });

  function reset() {
    setFile(null);
    setPreview(null);
    if (inputRef.current) inputRef.current.value = '';
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) reset();
        onOpenChange(next);
      }}
    >
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>{t('title')}</DialogTitle>
          <DialogDescription>{t('hint')}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" asChild>
              <a href={apiUrl('/api/v1/employees/import-template/')} download>
                <Download className="size-4" aria-hidden />
                {t('template')}
              </a>
            </Button>

            <input
              ref={inputRef}
              type="file"
              accept=".xlsx,.csv"
              aria-label={t('choose')}
              className="block w-full max-w-xs text-sm file:me-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-2 file:text-sm file:text-primary-foreground"
              onChange={(event) => {
                const chosen = event.target.files?.[0] ?? null;
                setFile(chosen);
                setPreview(null);
                if (chosen) upload.mutate(chosen);
              }}
            />
            {upload.isPending ? (
              <Loader2 className="size-4 animate-spin text-muted-foreground" aria-hidden />
            ) : null}
          </div>

          {preview ? (
            <>
              <div className="flex flex-wrap gap-2">
                <Badge variant="secondary">
                  {t('willCreate', { count: preview.summary.create })}
                </Badge>
                <Badge variant="secondary">
                  {t('willUpdate', { count: preview.summary.update })}
                </Badge>
                {preview.summary.failed > 0 ? (
                  <Badge variant="destructive">
                    {t('failed', { count: preview.summary.failed })}
                  </Badge>
                ) : null}
              </div>

              {preview.errors.length > 0 ? (
                <div className="max-h-48 overflow-auto rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('row')}</TableHead>
                        <TableHead>{tc('employee')}</TableHead>
                        <TableHead>{t('problems')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {preview.errors.map((row) => (
                        <TableRow key={`${row.row}-${row.code}`}>
                          <TableCell className="numeric">{row.row}</TableCell>
                          <TableCell>{row.name || row.code}</TableCell>
                          <TableCell className="text-destructive">
                            {row.errors.join(' · ')}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : null}

              {preview.valid.length > 0 ? (
                <div className="max-h-64 overflow-auto rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('row')}</TableHead>
                        <TableHead>{tc('employee')}</TableHead>
                        <TableHead>{tc('branch')}</TableHead>
                        <TableHead>{tc('amount')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {preview.valid.slice(0, 100).map((row) => (
                        <TableRow key={`${row.row}-${row.code}`}>
                          <TableCell className="numeric">{row.row}</TableCell>
                          <TableCell>
                            {row.name_ar}{' '}
                            <span className="numeric text-muted-foreground">({row.code})</span>
                          </TableCell>
                          <TableCell>{row.branch_name}</TableCell>
                          <TableCell className="numeric">{row.base_salary}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : null}
            </>
          ) : null}

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              {tc('cancel')}
            </Button>
            <Button
              disabled={!file || !preview || preview.valid.length === 0 || commit.isPending}
              onClick={() => file && commit.mutate(file)}
            >
              {commit.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Upload className="size-4" aria-hidden />
              )}
              {t('commit', { count: preview?.valid.length ?? 0 })}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
