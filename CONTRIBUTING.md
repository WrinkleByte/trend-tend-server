# Contributing

Thanks for helping. Bug reports, fixes, and features are welcome.

## Before your first pull request: sign the CLA

All contributions need a signed [Contributor License Agreement](CLA.md).
You keep the copyright to your work; the CLA gives WrinkleByte LLC a
license to use it, including under licenses other than AGPL-3.0 (for
example, in a future hosted service). Without it we can't merge your
change.

To sign, add this line to the description of your first pull request,
using your real name and the email on your commits:

    I have read and agree to the WrinkleByte CLA (CLA.md, version 1).
    Name: <your name>  Email: <your email>

If you are contributing on behalf of your employer, they need to agree
too. Email support@wrinklebyte.com first.

## Making a change

- Read [`docs/architecture.md`](docs/architecture.md) before changing the
  data model or sync protocol, and the architectural invariants in
  [`docs/development.md`](docs/development.md).
- Backend: `cd backend && .venv/bin/pytest` (needs the Postgres from
  `docker-compose.yml`) and `.venv/bin/ruff check .` must pass.
- Web: `npm run build` and `npm run lint` in `web/` must pass.
- Keep pull requests focused on one change, and describe what and why.
<!-- REUSE-IgnoreStart -->
- Start every new source file with the two-line SPDX header the other
  files use (`SPDX-FileCopyrightText: 2026 WrinkleByte LLC` and
  `SPDX-License-Identifier: AGPL-3.0-only`, in that file type's comment
  syntax). Check with `docker run --rm -v "$PWD":/data fsfe/reuse lint`.
<!-- REUSE-IgnoreEnd -->

## License

By contributing you agree that your contribution is licensed under
AGPL-3.0-only (see [LICENSE](LICENSE)) and under the terms of the
[CLA](CLA.md).
