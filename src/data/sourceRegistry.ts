import type { DataSourceDefinition } from "../core/domain";
/** Sources are registered only after access, licensing, and reliability checks. */
export const sourceRegistry: DataSourceDefinition[] = [];
