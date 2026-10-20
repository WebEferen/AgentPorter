// Copy to Bindings.kt next to PorterHarness.kt. One entry per source call id in .porter/fixtures; nothing else.
// Arguments arrive decoded: JSON integers are Long, floats Double, $bytes ByteArray, $set Set, $map Map.
// Bindings translate calling conventions only: never convert or patch a return value.
package porter

import com.acme.mylib.Counter
import com.acme.mylib.DEFAULT_SEPARATOR
import com.acme.mylib.Ms
import com.acme.mylib.slugify

val bindings: Map<String, Binding> = mapOf(
    // A JavaScript options object becomes a named argument; a null result was JavaScript undefined.
    "ms:default" to { args, _, _ ->
        val long = (args.getOrNull(1) as? Map<*, *>)?.get("long") == true
        Ms.ms(args[0], long = long) ?: Undefined
    },

    // Python keyword arguments map to Kotlin named arguments.
    "slugify.slugify:slugify" to { args, kwargs, _ ->
        slugify(args[0] as String, separator = kwargs["separator"] as String? ?: "-")
    },

    // <Class>.<method>: build the receiver from input["init"], then call the method.
    "pkg.mod:Counter.inc" to { args, _, input ->
        val init = input["init"] as Map<*, *>
        Counter(((init["args"] as List<*>)[0] as Long).toInt()).inc((args[0] as Long).toInt())
    },

    // Constant reads (input is {}).
    "slugify.slugify:DEFAULT_SEPARATOR" to { _, _, _ -> DEFAULT_SEPARATOR },
)
