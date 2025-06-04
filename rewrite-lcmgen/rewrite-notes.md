Proposal: Rewrite `lcmgen`

## Why 
C has a sharp edge and LCM has calcified wounds.

`lcmgen` -
* Intentionally leaks memory.
  * Mixed opinions on acceptability for short lived programs.
* Does roundabout methods of string processing.
  * Tries to do most manipulation via fwrite with intention to avoid allocations.
  * Consequently, helpful straightforward temporaries that would have multiple uses, just don't exist.
* Suffers from C `void*` weak typing.
* Is uninviting to hack at.
  * Not many people contributing.
  * All language targets have historically not seen feature parity.

## Options

C++: With C++ 20 `std::format` or fmtlib, string processing gets more ergonomic. But dependencies aside, C++ would still not be my goto for this.

Rust: Its the hotness. But nothing in the LCM toolchain supports Rust. Can't assume any LCM users installing form source would have the tooling available.

Python: Even people using LCM for embedded C or whatever probably have Python available on their dev box. Python can provide ***stronger*** type checking than C.

## Initial prototype

I began writing a direct translation of the C to Python. The `--debug` and `--tokenize` output matches in what I've tested. None of the language backends have been implemented yet.

Hand spot checking:

```
cd rewrite-lcmgen 

python3 main.py --tokenize ../test/types/lcmtest/comments_t.lcm > /tmp/new.txt
lcm-gen --tokenize ../test/types/lcmtest/comments_t.lcm > /tmp/base.txt
code -d /tmp/new.txt /tmp/base.txt 


lcm-gen --debug ../test/types/lcmtest/comments_t.lcm > /tmp/base.txt
python3 main.py --debug ../test/types/lcmtest/comments_t.lcm > /tmp/new.txt 
code --diff /tmp/new.txt /tmp/base.txt 
```

