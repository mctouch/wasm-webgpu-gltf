/* tslint:disable */
/* eslint-disable */

export class Renderer {
    private constructor();
    free(): void;
    [Symbol.dispose](): void;
    static init(canvas: HTMLCanvasElement): Promise<Renderer>;
    render(): void;
    resize(width: number, height: number): void;
}

export type InitInput = RequestInfo | URL | Response | BufferSource | WebAssembly.Module;

export interface InitOutput {
    readonly memory: WebAssembly.Memory;
    readonly __wbg_renderer_free: (a: number, b: number) => void;
    readonly renderer_init: (a: any) => any;
    readonly renderer_render: (a: number) => void;
    readonly renderer_resize: (a: number, b: number, c: number) => void;
    readonly wasm_bindgen_75c864e7351c0a8d___convert__closures_____invoke___js_sys_c5dbb73a0e4adf94___Function_fn_wasm_bindgen_75c864e7351c0a8d___JsValue_____wasm_bindgen_75c864e7351c0a8d___sys__Undefined___js_sys_c5dbb73a0e4adf94___Function_fn_wasm_bindgen_75c864e7351c0a8d___JsValue_____wasm_bindgen_75c864e7351c0a8d___sys__Undefined_______true_: (a: number, b: number, c: any, d: any) => void;
    readonly wasm_bindgen_75c864e7351c0a8d___convert__closures_____invoke___wasm_bindgen_75c864e7351c0a8d___JsValue__core_ed718c3d60ebd546___result__Result_____wasm_bindgen_75c864e7351c0a8d___JsError___true_: (a: number, b: number, c: any) => [number, number];
    readonly __wbindgen_malloc: (a: number, b: number) => number;
    readonly __wbindgen_realloc: (a: number, b: number, c: number, d: number) => number;
    readonly __wbindgen_exn_store: (a: number) => void;
    readonly __externref_table_alloc: () => number;
    readonly __wbindgen_externrefs: WebAssembly.Table;
    readonly __wbindgen_destroy_closure: (a: number, b: number) => void;
    readonly __externref_table_dealloc: (a: number) => void;
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
