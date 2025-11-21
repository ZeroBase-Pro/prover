module circom-prover

go 1.22

toolchain go1.22.1

require (
	github.com/consensys/gnark v0.12.1-0.20250406100832-60aade619880
	github.com/consensys/gnark-crypto v0.17.1-0.20250326164229-5fd6610ac2a1
	github.com/fxamacker/cbor/v2 v2.7.0
	github.com/google/uuid v1.6.0
	github.com/ingonyama-zk/icicle-gnark/v3 v3.2.2
	github.com/rs/zerolog v1.33.0
	github.com/stretchr/testify v1.10.0
	google.golang.org/grpc v1.64.0
	google.golang.org/protobuf v1.33.0
)

require (
	github.com/bits-and-blooms/bitset v1.20.0 // indirect
	github.com/blang/semver/v4 v4.0.0 // indirect
	github.com/consensys/bavard v0.1.31-0.20250314194434-b30d4344e6d4 // indirect
	github.com/davecgh/go-spew v1.1.1 // indirect
	github.com/google/pprof v0.0.0-20240727154555-813a5fbdbec8 // indirect
	github.com/mattn/go-colorable v0.1.13 // indirect
	github.com/mattn/go-isatty v0.0.20 // indirect
	github.com/mmcloughlin/addchain v0.4.0 // indirect
	github.com/pmezard/go-difflib v1.0.0 // indirect
	github.com/ronanh/intcomp v1.1.0 // indirect
	github.com/x448/float16 v0.8.4 // indirect
	golang.org/x/crypto v0.33.0 // indirect
	golang.org/x/net v0.24.0 // indirect
	golang.org/x/sync v0.11.0 // indirect
	golang.org/x/sys v0.30.0 // indirect
	golang.org/x/text v0.22.0 // indirect
	google.golang.org/genproto v0.0.0-20230410155749-daa745c078e1 // indirect
	gopkg.in/yaml.v3 v3.0.1 // indirect
	rsc.io/tmplfunc v0.0.3 // indirect
)

replace github.com/consensys/gnark v0.11.0 => github.com/ingonyama-zk/gnark v0.0.0-20241119105559-429d02d5f479

replace github.com/consensys/gnark-crypto v0.14.0 => github.com/consensys/gnark-crypto v0.12.2-0.20240423164836-7edca0e476c5
