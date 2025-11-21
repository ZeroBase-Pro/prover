package main

import (
	"encoding/hex"
	"errors"
	"fmt"
	"math/big"

	"github.com/consensys/gnark/backend/groth16"
	"github.com/consensys/gnark/backend/witness"
	"github.com/consensys/gnark/std/math/emulated"

	fr_bn254 "github.com/consensys/gnark-crypto/ecc/bn254/fr"
	"github.com/consensys/gnark-crypto/ecc/secp256k1/ecdsa"
	"github.com/consensys/gnark-crypto/ecc/secp256k1/fp"
	"github.com/consensys/gnark/frontend"
	"github.com/ethereum/go-ethereum/crypto/secp256k1"
	"golang.org/x/crypto/sha3"
)

func RunProveExportResult(proof groth16.Proof, witnessPublic witness.Witness) []string {
	_proof, ok := proof.(interface{ MarshalSolidity() []byte })
	if !ok {
		panic("proof does not implement MarshalSolidity()")
	}
	proofBytes := _proof.MarshalSolidity()

	// parse public inputs
	bPublicWitness, err := witnessPublic.MarshalBinary()
	if err != nil {
		panic(err)
	}
	bPublicWitness = bPublicWitness[12:]
	inputHex := hex.EncodeToString(bPublicWitness)
	inputBytes, err := hex.DecodeString(inputHex)
	if err != nil {
		panic(err)
	}
	if len(inputBytes)%fr_bn254.Bytes != 0 {
		panic("inputBytes mod fr.Bytes != 0")
	}
	nbPublicInputs := len(witnessPublic.Vector().(fr_bn254.Vector))
	nbInputs := len(inputBytes) / fr_bn254.Bytes
	if nbInputs != nbPublicInputs {
		panic("nbInputs != nbPublicInputs")
	}
	input := make([]*big.Int, nbPublicInputs)
	for i := 0; i < nbInputs; i++ {
		var e fr_bn254.Element
		e.SetBytes(inputBytes[fr_bn254.Bytes*i : fr_bn254.Bytes*(i+1)])
		input[i] = new(big.Int)
		e.BigInt(input[i])
	}

	// parse proof elements (always present)
	fpSize := 4 * 8 // 32
	if len(proofBytes) < fpSize*8 {
		panic("proofBytes too short for basic proof elements")
	}
	proofInts := make([]*big.Int, 8)
	for i := 0; i < 8; i++ {
		proofInts[i] = new(big.Int).SetBytes(proofBytes[fpSize*i : fpSize*(i+1)])
	}

	offset := fpSize * 8
	var commitments []*big.Int
	var commitmentsPok []*big.Int

	// try to parse commitments / CommitmentPok if present
	if len(proofBytes) > offset {
		// skip 4-byte separator (as in your runGroth16 logic)
		if len(proofBytes) < offset+4 {
			panic("unexpected format: missing commitment section header")
		}
		offset += 4

		const NbCommitments = 1
		commitments = make([]*big.Int, 2*NbCommitments)
		for i := 0; i < 2*NbCommitments; i++ {
			if len(proofBytes) < offset+fpSize {
				panic("proofBytes too short for commitments")
			}
			commitments[i] = new(big.Int).SetBytes(proofBytes[offset : offset+fpSize])
			offset += fpSize
		}

		// skip 4-byte separator before CommitmentPok
		if len(proofBytes) < offset+4 {
			panic("unexpected format: missing CommitmentPok section header")
		}

		commitmentsPok = make([]*big.Int, 2)
		for i := 0; i < 2; i++ {
			if len(proofBytes) < offset+fpSize {
				panic("proofBytes too short for CommitmentPok")
			}
			commitmentsPok[i] = new(big.Int).SetBytes(proofBytes[offset : offset+fpSize])
			offset += fpSize
		}
	}

	// collect result strings in order: proof, commitments (if any), pok (if any), public inputs
	var result []string
	for _, bi := range proofInts {
		result = append(result, bi.String())
	}
	for _, bi := range commitments {
		result = append(result, bi.String())
	}
	for _, bi := range commitmentsPok {
		result = append(result, bi.String())
	}
	for _, bi := range input {
		result = append(result, bi.String())
	}
	return result
}

func ComputeEthereumAddress(pubKey *ecdsa.PublicKey) []byte {
	pubKeyBytes := pubKey.Bytes()
	pubKeyBytes = pubKeyBytes[:]

	hash := sha3.NewLegacyKeccak256()
	hash.Write(pubKeyBytes)
	hashed := hash.Sum(nil)
	address := hashed[12:]

	return address
}

func BigEndianBytesToVar(api frontend.API, data []frontend.Variable) frontend.Variable {
	x := frontend.Variable(0)

	for i := 0; i < 20; i++ {
		x = api.Mul(x, frontend.Variable(256))
		x = api.Add(x, data[i])
	}
	return x
}

func privateKeyToHex(priv *ecdsa.PrivateKey) string {
	hexStr := priv.Bytes()[64:]
	addr := fmt.Sprintf("%x", hexStr)
	return addr
}

func isValidEthereumPrivateKey(hexKey string) bool {
	if len(hexKey) != 64 {
		return false
	}

	privBytes, err := hex.DecodeString(hexKey)
	if err != nil {
		return false
	}
	privKey := new(big.Int).SetBytes(privBytes)

	n := secp256k1.S256().N
	if privKey.Cmp(big.NewInt(1)) < 0 || privKey.Cmp(n) >= 0 {
		return false
	}

	return true
}

type ElementRaw struct {
	Limbs []uint64 `json:"Limbs"`
}

type AffinePointRaw struct {
	X ElementRaw `json:"X"`
	Y ElementRaw `json:"Y"`
}

type FancasterAnonymousCircuitRaw struct {
	Message   ElementRaw     `json:"Message"`
	V         interface{}    `json:"V"` // can be string, int, or uint64
	R         ElementRaw     `json:"R"`
	S         ElementRaw     `json:"S"`
	Expected  AffinePointRaw `json:"Expected"`
	RootHash  *big.Int       `json:"RootHash"` // same here
	Index     interface{}    `json:"Index"`
	Path      []*big.Int     `json:"Path"`
	ProjectId interface{}    `json:"ProjectId"`
}

func toElementFr(raw ElementRaw) (emulated.Element[emulated.Secp256k1Fr], error) {
	fe := emulated.Element[emulated.Secp256k1Fr]{}
	if len(raw.Limbs) != 4 {
		return fe, errors.New("expected 4 limbs for Fr")
	}
	fe.Limbs = make([]frontend.Variable, 4)
	for i := 0; i < 4; i++ {
		fe.Limbs[i] = raw.Limbs[i]
	}

	return fe, nil
}

func toElementFp(raw ElementRaw) (emulated.Element[emulated.Secp256k1Fp], error) {
	fp := emulated.Element[emulated.Secp256k1Fp]{}
	if len(raw.Limbs) != 4 {
		return fp, errors.New("expected 4 limbs for Fp")
	}
	fp.Limbs = make([]frontend.Variable, 4)
	for i := 0; i < 4; i++ {
		fp.Limbs[i] = raw.Limbs[i]
	}
	return fp, nil
}

func toFrontendVar(v interface{}) frontend.Variable {
	switch val := v.(type) {
	case float64:
		return big.NewInt(int64(val))
	case string:
		bi := new(big.Int)
		bi.SetString(val, 10)
		return bi
	case int:
		return big.NewInt(int64(val))
	case uint64:
		return big.NewInt(0).SetUint64(val)
	default:
		return v
	}
}

func Convert(raw FancasterAnonymousCircuitRaw) (FancasterAnonymousCircuit, error) {
	var circuit FancasterAnonymousCircuit
	var err error

	circuit.Message, err = toElementFr(raw.Message)
	if err != nil {
		return circuit, err
	}

	circuit.V = toFrontendVar(raw.V)

	circuit.R, err = toElementFr(raw.R)
	if err != nil {
		return circuit, err
	}

	circuit.S, err = toElementFr(raw.S)
	if err != nil {
		return circuit, err
	}

	circuit.Expected.X, err = toElementFp(raw.Expected.X)
	if err != nil {
		return circuit, err
	}

	circuit.Expected.Y, err = toElementFp(raw.Expected.Y)
	if err != nil {
		return circuit, err
	}

	circuit.RootHash = toFrontendVar(raw.RootHash)
	circuit.Index = toFrontendVar(raw.Index)
	circuit.ProjectId = toFrontendVar(raw.ProjectId)

	if len(raw.Path) != 14 {
		return circuit, fmt.Errorf("expected Path of length 14, got %d", len(raw.Path))
	}

	for i := 0; i < 14; i++ {
		circuit.Path[i] = toFrontendVar(raw.Path[i])
	}

	return circuit, nil
}

func Pub2AddrHint(_ *big.Int, inputs []*big.Int, outputs []*big.Int) error {
	if len(inputs) != 8 {
		return fmt.Errorf("expected 8 inputs, got %d", len(inputs))
	}

	var x fp.Element
	x.SetBigInt(inputs[0])
	for i := 1; i < 4; i++ {
		var z fp.Element
		limbs := new(big.Int).Exp(big.NewInt(2), big.NewInt(64), nil)
		z.SetBigInt(limbs)

		var a fp.Element
		a.SetBigInt(inputs[i])
		x.Mul(&x, &z).Add(&x, &a)
	}

	var y fp.Element
	y.SetBigInt(inputs[4])
	for i := 5; i < 8; i++ {
		var z fp.Element
		limbs := new(big.Int).Exp(big.NewInt(2), big.NewInt(64), nil)
		z.SetBigInt(limbs)

		var a fp.Element
		a.SetBigInt(inputs[i])
		y.Mul(&y, &z).Add(&y, &a)
	}

	pubBytes := make([]byte, 65)
	pubBytes[0] = 0x04
	xBytes := x.Bytes()
	yBytes := y.Bytes()
	copy(pubBytes[1:33], xBytes[:])
	copy(pubBytes[33:], yBytes[:])

	for i := 0; i < 64; i++ {
		outputs[i] = big.NewInt(int64(pubBytes[i+1]))
	}

	return nil
}
