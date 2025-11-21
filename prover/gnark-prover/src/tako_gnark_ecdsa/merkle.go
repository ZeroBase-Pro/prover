package tako_gnark_ecdsa

import (
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/std/accumulator/merkle"
	"github.com/consensys/gnark/std/hash/mimc"
)

func MerkleTreeVerify(api frontend.API, rootHash frontend.Variable, merklePath []frontend.Variable, proofIndex frontend.Variable) error {
	hsh, err := mimc.NewMiMC(api)
	if err != nil {
		return err
	}
	var M merkle.MerkleProof
	M.RootHash = rootHash
	M.Path = merklePath
	M.VerifyProof(api, &hsh, proofIndex)
	return nil
}
