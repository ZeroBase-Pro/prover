package tako_gnark_ecdsa

import (
	"fmt"
	"log"
	"math/big"

	"github.com/consensys/gnark-crypto/ecc/secp256k1"
	"github.com/consensys/gnark-crypto/ecc/secp256k1/ecdsa"
	"github.com/consensys/gnark-crypto/ecc/secp256k1/fp"
	"github.com/consensys/gnark/constraint/solver"
)

const (
	// Field element constants
	LimbSize = 64 // Size of each limb in bits
	Base2_64 = 2  // Base for 64-bit calculations

	// Input/output counts
	ExpectedInputs  = 8  // 4 for X coordinate and 4 for Y coordinate
	ExpectedOutputs = 64 // Public key bytes (without 0x04 prefix)
)

// Pub2AddrHint calculates Ethereum address from public key coordinates
func Pub2AddrHint(_ *big.Int, inputs []*big.Int, outputs []*big.Int) error {
	// Expecting 8 inputs: 4 for X coordinate and 4 for Y coordinate
	if len(inputs) != ExpectedInputs {
		return fmt.Errorf("expected %d inputs, got %d", ExpectedInputs, len(inputs))
	}

	// Reconstruct X coordinate from 4 parts
	var x fp.Element
	x.SetBigInt(inputs[0])
	for i := 1; i < 4; i++ {
		var z fp.Element
		limbs := new(big.Int).Exp(big.NewInt(Base2_64), big.NewInt(LimbSize), nil)
		z.SetBigInt(limbs)

		var a fp.Element
		a.SetBigInt(inputs[i])
		x.Mul(&x, &z).Add(&x, &a)
	}

	// Reconstruct Y coordinate from 4 parts
	var y fp.Element
	y.SetBigInt(inputs[4])
	for i := 5; i < 8; i++ {
		var z fp.Element
		limbs := new(big.Int).Exp(big.NewInt(Base2_64), big.NewInt(LimbSize), nil)
		z.SetBigInt(limbs)

		var a fp.Element
		a.SetBigInt(inputs[i])
		y.Mul(&y, &z).Add(&y, &a)
	}

	// Create public key
	pubKey := ecdsa.PublicKey{
		A: secp256k1.G1Affine{
			X: x,
			Y: y,
		},
	}
	addrBy := ComputeEthereumAddress(&pubKey)
	log.Printf("address %x", addrBy)

	// Convert to uncompressed public key bytes (65 bytes: 0x04 || X || Y)
	pubBytes := make([]byte, 65)
	pubBytes[0] = 0x04
	xBytes := x.Bytes()
	yBytes := y.Bytes()
	copy(pubBytes[1:33], xBytes[:])
	copy(pubBytes[33:], yBytes[:])

	// Set output
	for i := 0; i < ExpectedOutputs; i++ {
		outputs[i] = big.NewInt(int64(pubBytes[i+1]))
	}

	return nil
}

// Register Hint
func init() {
	solver.RegisterHint(Pub2AddrHint)
	key := solver.GetHintID(Pub2AddrHint)
	name := solver.GetHintName(Pub2AddrHint)
	log.Printf("pub2addr init %d %s", key, name)
}
