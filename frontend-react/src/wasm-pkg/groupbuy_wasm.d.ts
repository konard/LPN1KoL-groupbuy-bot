/* tslint:disable */
/* eslint-disable */

/**
 * Aggregate procurement statistics from a JSON array
 * Returns JSON object with: total_count, active_count, total_amount, total_target,
 * overall_progress, avg_participants, cities (unique), by_status counts
 */
export function aggregate_procurement_stats(json_input: string): string;

/**
 * Batch-process messages: format text, compute date groups, format times
 * Input: JSON array of messages, current user ID
 * Output: JSON array with formatted fields
 */
export function batch_process_messages(json_input: string, current_user_id: bigint): string;

/**
 * Batch-process procurements: compute progress, days left, and format currency in one pass
 * Input: JSON array of procurements
 * Output: JSON array with computed fields added
 */
export function batch_process_procurements(json_input: string): string;

/**
 * Run a performance benchmark for batch processing
 * Generates N random procurements and processes them, returning elapsed time in ms
 */
export function benchmark_batch_processing(count: number): number;

/**
 * Calculate procurement progress percentage
 */
export function calculate_progress(current_amount: number, target_amount: number): number;

/**
 * Calculate days remaining until deadline
 */
export function days_until(deadline_ms: number): number;

/**
 * Escape HTML to prevent XSS
 */
export function escape_html(text: string): string;

/**
 * Format currency amount (Russian rubles)
 */
export function format_currency(amount: number): string;

/**
 * Format message text: escape HTML, convert URLs to links, convert newlines to <br>
 */
export function format_message_text(text: string): string;

/**
 * Format relative time in Russian
 */
export function format_relative_time(timestamp_ms: number): string;

/**
 * Generate unique platform user ID for websocket users
 */
export function generate_platform_user_id(): string;

/**
 * Generate avatar background color based on name (hash-based)
 */
export function get_avatar_color(name: string): string;

/**
 * Get initials from first name and last name
 */
export function get_initials(first_name: string, last_name: string): string;

/**
 * Search within messages by text content
 * Returns JSON array of matching message indices
 */
export function search_messages(json_input: string, query: string): string;

/**
 * Fuzzy search procurements by query string
 * Returns JSON array of matching procurement IDs with relevance scores, sorted by relevance
 */
export function search_procurements(json_input: string, query: string): string;

/**
 * Sort procurements by a specified field
 * sort_by: "title", "amount", "progress", "deadline", "participants", "created"
 * order: "asc" or "desc"
 * Returns JSON array of sorted procurement IDs
 */
export function sort_procurements(json_input: string, sort_by: string, order: string): string;

/**
 * Validate email format
 */
export function validate_email(email: string): boolean;

/**
 * Validate phone number format (Russian phone number)
 */
export function validate_phone(phone: string): boolean;

/**
 * Validate procurement form data
 * Returns JSON string with validation errors (empty object if valid)
 */
export function validate_procurement_form(title: string, description: string, city: string, target_amount: number, deadline_ms: number): string;

export type InitInput = RequestInfo | URL | Response | BufferSource | WebAssembly.Module;

export interface InitOutput {
    readonly memory: WebAssembly.Memory;
    readonly aggregate_procurement_stats: (a: number, b: number) => [number, number];
    readonly batch_process_messages: (a: number, b: number, c: bigint) => [number, number];
    readonly batch_process_procurements: (a: number, b: number) => [number, number];
    readonly benchmark_batch_processing: (a: number) => number;
    readonly calculate_progress: (a: number, b: number) => number;
    readonly escape_html: (a: number, b: number) => [number, number];
    readonly format_currency: (a: number) => [number, number];
    readonly format_message_text: (a: number, b: number) => [number, number];
    readonly format_relative_time: (a: number) => [number, number];
    readonly generate_platform_user_id: () => [number, number];
    readonly get_avatar_color: (a: number, b: number) => [number, number];
    readonly get_initials: (a: number, b: number, c: number, d: number) => [number, number];
    readonly search_messages: (a: number, b: number, c: number, d: number) => [number, number];
    readonly search_procurements: (a: number, b: number, c: number, d: number) => [number, number];
    readonly sort_procurements: (a: number, b: number, c: number, d: number, e: number, f: number) => [number, number];
    readonly validate_email: (a: number, b: number) => number;
    readonly validate_phone: (a: number, b: number) => number;
    readonly validate_procurement_form: (a: number, b: number, c: number, d: number, e: number, f: number, g: number, h: number) => [number, number];
    readonly days_until: (a: number) => number;
    readonly __wbindgen_externrefs: WebAssembly.Table;
    readonly __wbindgen_malloc: (a: number, b: number) => number;
    readonly __wbindgen_realloc: (a: number, b: number, c: number, d: number) => number;
    readonly __wbindgen_free: (a: number, b: number, c: number) => void;
    readonly __wbindgen_start: () => void;
}

export type SyncInitInput = BufferSource | WebAssembly.Module;

/**
 * Instantiates the given `module`, which can either be bytes or
 * a precompiled `WebAssembly.Module`.
 *
 * @param {{ module: SyncInitInput }} module - Passing `SyncInitInput` directly is deprecated.
 *
 * @returns {InitOutput}
 */
export function initSync(module: { module: SyncInitInput } | SyncInitInput): InitOutput;

/**
 * If `module_or_path` is {RequestInfo} or {URL}, makes a request and
 * for everything else, calls `WebAssembly.instantiate` directly.
 *
 * @param {{ module_or_path: InitInput | Promise<InitInput> }} module_or_path - Passing `InitInput` directly is deprecated.
 *
 * @returns {Promise<InitOutput>}
 */
export default function __wbg_init (module_or_path?: { module_or_path: InitInput | Promise<InitInput> } | InitInput | Promise<InitInput>): Promise<InitOutput>;
