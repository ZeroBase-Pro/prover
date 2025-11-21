package utils

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"math/big"
	"os"
	"strconv"

	"circom-prover/lib/logger"

	"github.com/consensys/gnark-crypto/ecc/bn254/fr"
	fr_bn254 "github.com/consensys/gnark-crypto/ecc/bn254/fr"
	"github.com/consensys/gnark/backend/groth16"
	"github.com/consensys/gnark/backend/witness"
	"github.com/consensys/gnark/frontend"
)

// Uint8ToBits converts a byte slice to a binary string representation
func Uint8ToBits(data []byte) string {
	result := ""
	for _, byteVal := range data {
		result += fmt.Sprintf("%08b", byteVal)
	}
	return result
}

func ReconstructJWTFromSegments(segments [][]string) (string, error) {
	var buf []byte
	for _, seg := range segments {
		for _, s := range seg {
			u, err := strconv.ParseUint(s, 10, 8)
			if err != nil {
				return "", fmt.Errorf("parse byte %q: %w", s, err)
			}
			buf = append(buf, byte(u))
		}
	}
	if len(buf) < 8 {
		return "", fmt.Errorf("buffer too small")
	}

	i := len(buf)
	for i >= 8 {
		block := buf[i-8 : i]
		allZero := true
		for _, b := range block {
			if b != 0 {
				allZero = false
				break
			}
		}
		if allZero {
			i -= 8
			continue
		}

		bits := binary.BigEndian.Uint32(block[4:8])
		msgLen := int(bits / 8)
		if msgLen < 0 || msgLen > len(buf) {
			return "", fmt.Errorf("invalid message length %d", msgLen)
		}
		return string(buf[:msgLen]), nil
	}
	return "", fmt.Errorf("length field not found")
}

func ShaHash(data []byte) []byte {
	hash := sha256.Sum256(data)
	return hash[:]
}

func MergeJWT(jwtSegments [][]string) []byte {
	var merged []byte
	for _, segment := range jwtSegments {
		for _, str := range segment {
			val, _ := strconv.Atoi(str)
			merged = append(merged, byte(val))
		}
	}
	return merged
}

// ConvertToBinaryString converts interface slice to binary string
func ConvertToBinaryString(jwtSha256 []interface{}) string {
	var binaryString string
	for _, v := range jwtSha256 {
		binaryString += v.(string)
	}
	return binaryString
}

// GenerateUniqueFilename creates a unique filename with the given base, extension, and ID
func GenerateUniqueFilename(base string, ext string, id string) string {
	return fmt.Sprintf("%s_%s.%s", base, id, ext)
}

// SaveInputAsJSON saves input data as JSON file
func SaveInputAsJSON(inputs []int, filename string) error {
	data := map[string][]int{
		"inputs": inputs,
	}
	jsonData, err := json.Marshal(data)
	if err != nil {
		return err
	}

	file, err := os.Create(filename)
	if err != nil {
		return err
	}
	defer file.Close()

	_, err = file.Write(jsonData)
	return err
}

func ParseWtns(filePath string, NumOutput uint32, NumInPublic uint32) ([]frontend.Variable, []frontend.Variable, error) {
	fileContent, err := ioutil.ReadFile(filePath)
	if err != nil {
		return nil, nil, fmt.Errorf("error reading file: %v", err)
	}

	if string(fileContent[:4]) != "wtns" {
		return nil, nil, fmt.Errorf("invalid file format")
	}

	rawPrimeStart := 28
	rawPrimeEnd := rawPrimeStart + int(8)*4

	witnessSize := binary.LittleEndian.Uint32(fileContent[rawPrimeEnd : rawPrimeEnd+4])
	lg := logger.Logger()
	lg.Info().Msgf("Witness Size: %d", witnessSize)

	witnesses := make([]frontend.Variable, 0, witnessSize-NumInPublic-NumOutput)
	witnessesPublic := make([]frontend.Variable, NumInPublic+NumOutput)

	idSection2Start := rawPrimeEnd + 4

	witnessDataStart := idSection2Start + 12
	witnessDataLength := int(8 * 4)
	for i := uint32(0); i < witnessSize; i++ {
		witnessStart := witnessDataStart + int(i)*witnessDataLength
		witnessEnd := witnessStart + witnessDataLength
		witness := fileContent[witnessStart:witnessEnd]
		//witnesses[i] = new(big.Int).SetBytes(witness)
		witness = convertLittleEndianToBigEndian(witness)
		bigIntWitness := new(big.Int).SetBytes(witness)

		if i >= 1 && i < NumOutput+1+NumInPublic {
			witnessesPublic[i-1] = bigIntWitness
			lg := logger.Logger()
			lg.Debug().Msgf("witness value: %s", bigIntWitness.String())
			// Debug: print specific witness and public input values when debug logging is enabled
		} else {
			witnesses = append(witnesses, bigIntWitness)
		}
	}

	return witnesses, witnessesPublic, nil
}

func convertLittleEndianToBigEndian(data []byte) []byte {
	for i := 0; i < len(data)/2; i++ {
		data[i], data[len(data)-1-i] = data[len(data)-1-i], data[i]
	}
	return data
}

func RunProveExportResult(proof groth16.Proof, witnessPublic witness.Witness) []string {
	_proof, ok := proof.(interface{ MarshalSolidity() []byte })
	if !ok {
		panic("proof does not implement MarshalSolidity()")
	}
	proofStr := hex.EncodeToString(_proof.MarshalSolidity())
	bPublicWitness, err := witnessPublic.MarshalBinary()
	if err != nil {
		panic(err)
	}
	bPublicWitness = bPublicWitness[12:]
	publicWitnessStr := hex.EncodeToString(bPublicWitness)
	proofHex := proofStr
	inputHex := publicWitnessStr
	nbPublicInputs := len(witnessPublic.Vector().(fr_bn254.Vector))
	fpSize := 4 * 8
	proofBytes, err := hex.DecodeString(proofHex)
	if err != nil {
		panic(err)
	}
	if len(proofBytes) != fpSize*8 {
		panic("proofBytes != fpSize*8")
	}
	inputBytes, err := hex.DecodeString(inputHex)
	if err != nil {
		panic(err)
	}
	if len(inputBytes)%fr.Bytes != 0 {
		panic("inputBytes mod fr.Bytes !=0")
	}
	nbInputs := len(inputBytes) / fr.Bytes
	if nbInputs != nbPublicInputs {
		panic("nbInputs != nbPublicInputs")
	}
	input := make([]*big.Int, nbPublicInputs)
	for i := 0; i < nbInputs; i++ {
		var e fr.Element
		e.SetBytes(inputBytes[fr.Bytes*i : fr.Bytes*(i+1)])
		input[i] = new(big.Int)
		e.BigInt(input[i])
	}
	var __proof [8]*big.Int
	for i := 0; i < 8; i++ {
		__proof[i] = new(big.Int).SetBytes(proofBytes[fpSize*i : fpSize*(i+1)])
	}
	var finalproof []string
	var finalinput []string
	for _, bi := range __proof {
		finalproof = append(finalproof, bi.String())
	}
	for _, bi := range input {
		finalinput = append(finalinput, bi.String())
	}
	var result []string
	result = append(result, finalproof...)
	result = append(result, finalinput...)
	return result
}
