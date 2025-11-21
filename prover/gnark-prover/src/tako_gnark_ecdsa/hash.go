package tako_gnark_ecdsa

import (
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/std/hash/sha3"
	"github.com/consensys/gnark/std/math/uints"
)

func Keccak256(api frontend.API, in [64]uints.U8) ([]uints.U8, error) {
	keccak256, err := sha3.NewLegacyKeccak256(api)
	if err != nil {
		return nil, err
	}

	api.Println("In: ", in)

	keccak256.Write(in[:])
	res := keccak256.Sum()

	return res, nil
}
