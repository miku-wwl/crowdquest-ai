# Third-party notices

CrowdQuest application/documentation is MIT-licensed under the root LICENSE.
AIG is a pre-existing dependency, not newly authored CrowdQuest code.

## Agentic Intent Gate v0.3.0

Source: https://github.com/miku-wwl/agentic-intent-gate

Release commit: `bb8e8fb1234128613a750bee17967b225072bb14`.
The following complete upstream notice is preserved:

```text
MIT License

Copyright (c) 2026 Weilai Wang

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Other installed dependencies remain separately licensed; consult installed distribution
metadata and bundled license files. The lockfile is a dependency inventory, not a grant
of relicensing rights. No frontend/media asset redistribution is included in Phase 0.

## Phase 4.5 WebM metadata helper

`@fix-webm-duration/fix==1.0.1` and `@fix-webm-duration/parser==1.0.1` are MIT-licensed.
Source: https://github.com/yusitnikov/fix-webm-duration . The complete upstream notice
(https://github.com/yusitnikov/fix-webm-duration/blob/master/LICENSE) is retained:

```text
The MIT license

Copyright (c) 2018 Yury Sitnikov

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

Its `tslib` dependency includes this notice (installed LICENSE.txt):

```text
Copyright (c) Microsoft Corporation.

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
PERFORMANCE OF THIS SOFTWARE.
```

## Optional OBS compatibility packages

Installed distribution metadata declares `obsws-python==1.8.0` as GPL-3.0-only and
`websocket-client==1.9.2` as Apache-2.0. Their own licenses remain applicable; they
are not relicensed by CrowdQuest's MIT notice. They are optional (`obs` extra) and
used in development fixture qualification, not required by the OBS-free core. No
OBS executable or SDK source is vendored here. The transient imageio-ffmpeg tool
used for local media inspection is not a project/runtime dependency or a bundled
binary. Consult that tool/binary's notices separately before redistributing it.
