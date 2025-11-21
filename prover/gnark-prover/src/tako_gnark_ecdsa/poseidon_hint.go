package tako_gnark_ecdsa

import (
	"log"
	"math/big"

	"github.com/consensys/gnark-crypto/ecc/bn254/fr"
	"github.com/consensys/gnark/constraint/solver"
)

func PoseidonHint(_ *big.Int, inputs []*big.Int, outputs []*big.Int) error {
	log.Printf("PoseidonHint inputs %v", inputs)
	leaf := inputs[0]
	index := inputs[1]
	path := inputs[2:]

	log.Printf("PoseidonHint rootHash %v", leaf)
	log.Printf("PoseidonHint index %v", index)
	log.Printf("PoseidonHint path %v", path)

	// Convert leaf to fr.Element
	var current fr.Element
	current.SetBigInt(leaf)

	// Output final root hash
	outputs[0] = new(big.Int)
	current.BigInt(outputs[0])

	log.Printf("PoseidonHint root output: %s", outputs[0].Text(10))
	return nil
}

// Register Hint
func init() {
	solver.RegisterHint(PoseidonHint)
}
