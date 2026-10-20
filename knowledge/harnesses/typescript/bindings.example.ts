// Copy to bindings.ts next to harness.ts. One entry per source call id in .porter/fixtures; nothing else.
// Bindings translate calling conventions only. Never convert or patch a return value here.
import type { Bindings } from "./harness.ts";
import { parse, format, slugify, Slugger, DEFAULT_SEPARATOR } from "../src/index.ts";

export const bindings: Bindings = {
  // Positional arguments map straight through.
  "ms:default": (args) => (typeof args[0] === "string" ? parse(args[0]) : format(args[0], args[1])),

  // Python keyword arguments become an options object.
  "slugify.slugify:slugify": (args, kwargs) => slugify(args[0], { separator: kwargs.separator, lowercase: kwargs.lowercase }),

  // <Class>.<method>: build the receiver from input.init (tags already decoded), then call the method.
  "pkg.mod:Slugger.slug": (args, _kwargs, input) => new Slugger(...(input.init?.args ?? [])).slug(args[0]),

  // Constant reads (input is {}): return the port's constant.
  "slugify.slugify:DEFAULT_SEPARATOR": () => DEFAULT_SEPARATOR,
};
