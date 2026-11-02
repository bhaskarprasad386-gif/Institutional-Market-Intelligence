import type { DataSourceDefinition } from "../core/domain";
/** Sources are registered only after access, licensing, and reliability checks. */
export const sourceRegistry: DataSourceDefinition[] = [
  { id: "user-file-import", name: "User supplied CSV / Excel", market: "USER_IMPORT", mode: "file-import", enabled: true, notes: "Manual user-selected files only. Source and market date are recorded; imported values are not independently verified." }
];
