'use client';

import {
  AllCommunityModule,
  ModuleRegistry,
  themeQuartz,
  type GridOptions,
} from 'ag-grid-community';
import { AgGridReact } from 'ag-grid-react';
import { useLocale } from 'next-intl';
import { useMemo } from 'react';

// AG Grid v33 requires explicit module registration.
ModuleRegistry.registerModules([AllCommunityModule]);

/** Quartz, restyled to match the app's shadcn tokens. */
const appTheme = themeQuartz.withParams({
  accentColor: 'hsl(222.2 47.4% 11.2%)',
  borderRadius: 6,
  headerFontWeight: 600,
  fontFamily: 'inherit',
  spacing: 6,
});

/**
 * Thin wrapper over AgGridReact that wires the two things every grid in this
 * app needs: right-to-left layout in Arabic, and a dense, keyboard-first default.
 */
export function DataGrid<T>(props: GridOptions<T> & { height?: number | string }) {
  const locale = useLocale();
  const { height = 560, defaultColDef, ...gridProps } = props;

  const mergedDefaults = useMemo(
    () => ({
      sortable: true,
      resizable: true,
      suppressMovable: true,
      ...(defaultColDef ?? {}),
    }),
    [defaultColDef],
  );

  return (
    <div style={{ height, width: '100%' }}>
      <AgGridReact<T>
        theme={appTheme}
        enableRtl={locale === 'ar'}
        animateRows={false}
        rowHeight={38}
        headerHeight={40}
        stopEditingWhenCellsLoseFocus
        {...gridProps}
        defaultColDef={mergedDefaults}
      />
    </div>
  );
}
