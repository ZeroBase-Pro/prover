package tako_gnark_ecdsa

import (
	"github.com/consensys/gnark-crypto/ecc/secp256k1/ecdsa"
	"github.com/consensys/gnark/frontend"
	"golang.org/x/crypto/sha3"
)

const (
	// Ethereum address constants
	EthereumAddrLen = 20 // Ethereum address length in bytes
	PubKeyBytesLen  = 64 // Public key length in bytes (without 0x04 prefix)
	HashOffset      = 12 // Offset to get address from hash (last 20 bytes)

	// Byte processing constants
	BitsPerByte = 8   // Number of bits per byte
	Base256     = 256 // Base for byte conversion
)

// ComputeEthereumAddress computes Ethereum address from public key
func ComputeEthereumAddress(pubKey *ecdsa.PublicKey) []byte {
	// Get uncompressed public key (64 bytes without 0x04 prefix)
	pubKeyBytes := pubKey.Bytes()

	// Calculate Keccak256 hash
	hash := sha3.NewLegacyKeccak256()
	hash.Write(pubKeyBytes)
	hashed := hash.Sum(nil)

	// Return last 20 bytes as Ethereum address
	return hashed[HashOffset:]
}

// BigEndianBytesToVar converts big-endian byte array to frontend.Variable
func BigEndianBytesToVar(api frontend.API, data []frontend.Variable) frontend.Variable {
	x := frontend.Variable(0)

	// Process each byte in big-endian order
	for i := 0; i < EthereumAddrLen; i++ {
		x = api.Mul(x, frontend.Variable(Base256)) // Left shift 8 bits
		x = api.Add(x, data[i])
	}
	return x
}
