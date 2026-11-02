export type DataStatus = "verified" | "stale" | "missing" | "imported" | "unverified";
export interface DataProvenance { sourceName:string; sourceUrl?:string; marketDate:string; retrievedAt:string; status:DataStatus; }
export interface Observation<T> { id:string; value:T; provenance:DataProvenance; }
export interface DataSourceDefinition { id:string; name:string; market:"NSE"|"BSE"|"GLOBAL"|"USER_IMPORT"; mode:"browser"|"file-import"|"manual"; enabled:boolean; notes:string; }
