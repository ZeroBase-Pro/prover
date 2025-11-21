package tako_gnark_ecdsa

import (
	"fmt"
	"log"

	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/std/algebra/emulated/sw_emulated"
	"github.com/consensys/gnark/std/evmprecompiles"
	"github.com/consensys/gnark/std/math/emulated"
	"github.com/consensys/gnark/std/math/uints"
)

const (
	// Circuit configuration
	MerklePathLength = 14

	// Project IDs
	FancasterProjectID = 10009
)

type Circuit struct {
	// Address Data
	Message  emulated.Element[emulated.Secp256k1Fr]
	V        frontend.Variable
	R        emulated.Element[emulated.Secp256k1Fr]
	S        emulated.Element[emulated.Secp256k1Fr]
	Expected sw_emulated.AffinePoint[emulated.Secp256k1Fp]
	//Address   frontend.Variable
	RootHash  frontend.Variable
	Index     frontend.Variable
	Path      [14]frontend.Variable
	ProjectId frontend.Variable `gnark:",public"`
}

func (circuit *Circuit) U8toR1(api frontend.API, target []uints.U8) frontend.Variable {
	var bits []frontend.Variable
	// Iterate over the U8 slice (assuming big-endian order)
	for i := 0; i < len(target); i++ {
		// Get the 8 bits of each U8
		u8Bits := bits[i] // Decompose U8 into its 8 bits
		// Prepend or append bits based on endianness
		bits = append(bits, u8Bits) // Big-endian: concatenate bits directly
	}

	// Convert the combined bits into a Secp256k1Fr element
	secpFieldVal := api.FromBinary(bits...)
	return secpFieldVal
}

func (circuit *Circuit) Define(api frontend.API) error {

	// 1. Recover public key through ecrecover
	// 2. Calculate address from public key
	// 3. Check if address exists in mkl
	api.AssertIsEqual(circuit.ProjectId, frontend.Variable(FancasterProjectID))
	res := evmprecompiles.ECRecover(api, circuit.Message, circuit.V, circuit.R, circuit.S, 0, 0)

	curve, err := sw_emulated.New[emulated.Secp256k1Fp, emulated.Secp256k1Fr](api, sw_emulated.GetSecp256k1Params())
	curve.AssertIsEqual(&circuit.Expected, res)

	pubBytes_noPrefix, err := api.Compiler().NewHint(Pub2AddrHint, PubKeyBytesLen,
		res.X.Limbs[3], res.X.Limbs[2], res.X.Limbs[1], res.X.Limbs[0],
		res.Y.Limbs[3], res.Y.Limbs[2], res.Y.Limbs[1], res.Y.Limbs[0])
	if err != nil {
		return fmt.Errorf("Pub2AddrHint hint: %w", err)
	}
	var hash_in [PubKeyBytesLen]uints.U8
	for i := 0; i < PubKeyBytesLen; i++ {
		hash_in[i].Val = pubBytes_noPrefix[i] // Assume uint8 -> uints.U8 conversion here
	}
	pubBytes_hash, err := Keccak256(api, hash_in)

	addressBytes := make([]frontend.Variable, EthereumAddrLen)
	for i := 0; i < EthereumAddrLen; i++ {
		addressBytes[i] = pubBytes_hash[i+HashOffset].Val
	}
	addr_fv := BigEndianBytesToVar(api, addressBytes)

	log.Println("addr_fv", addr_fv)
	log.Println("addressBytes", addressBytes)
	merklePath := make([]frontend.Variable, MerklePathLength)
	merklePath[0] = addr_fv
	for i := 1; i < len(merklePath); i++ {
		merklePath[i] = circuit.Path[i]
	}

	err = MerkleTreeVerify(api, circuit.RootHash, merklePath, circuit.Index)
	if err != nil {
		log.Printf("MerkleTreeVerify %s", err)
		return err
	}
	return nil
}
