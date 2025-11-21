package main

import (
	"bytes"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	pb "gnark-prover/src/protobuf"
	"io/ioutil"
	"log"
	"math/big"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/consensys/gnark/backend"
	"github.com/consensys/gnark/std/algebra/emulated/sw_emulated"
	"github.com/consensys/gnark/std/evmprecompiles"
	"github.com/consensys/gnark/std/math/bitslice"
	"github.com/consensys/gnark/std/math/emulated"
	"github.com/consensys/gnark/std/math/uints"

	"gnark-prover/src/tako_gnark_ecdsa"

	"github.com/consensys/gnark-crypto/ecc"
	"github.com/consensys/gnark-crypto/ecc/bn254/fr"
	"github.com/consensys/gnark/backend/groth16"
	"github.com/consensys/gnark/constraint"
	"github.com/consensys/gnark/constraint/solver"
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/std/math/bits"
	"google.golang.org/grpc"
)

// CircuitData holds the data for a circuit template
type CircuitData struct {
	Pk  groth16.ProvingKey
	Vk  groth16.VerifyingKey
	Ccs constraint.ConstraintSystem
	// NumOutput   uint32
	// NumInPublic uint32
	CircuitPath string
}

// server struct with circuits map to hold multiple circuit templates
type server struct {
	pb.UnimplementedProveServiceServer
	circuits          map[string]*CircuitData
	runningProveTasks int32
}

const (
	Version = "v1.0.0"

	// File paths
	InputFolderPath = "input"
	WtnsFolderPath  = "wtns"
	KeysFolderPath  = "keys"

	// File names
	PkFileName   = "pk.key"
	VkFileName   = "vk.key"
	R1csFileName = "circuit.ccs"
	DeviceType   = "CUDA"

	// Network configuration
	DefaultPort = 60050

	// Business logic constants
	SatoshiMultiplier = 100000000 // Convert to satoshis
	MaxLeverage       = 3
	MaxDelta          = 5
	BinanceProjectID  = 10005

	// Circuit configuration
	MerklePathLength = 14
	EthereumAddrLen  = 20
	PubKeyBytesLen   = 64
	HashBytesLen     = 32

	// Status codes
	STATUS_CODE_UNSUPPORT_CIRCUIT       = 100000
	STATUS_CODE_GPU_DEVICE_ERROR        = 100001
	STATUS_CODE_SHA256_NOT_MATCH        = 100002
	STATUS_CODE_JSON_FROMAT_ERROR       = 100003
	STATUS_CODE_INVALID_INPUT           = 100004
	STATUS_CODE_TO_WITNESS_ERROR        = 100005
	STATUS_CODE_TO_SECRET_WITNESS_ERROR = 100006
	STATUS_CODE_TO_PUBLIC_WITNESS_ERROR = 100007
	STATUS_CODE_GENERATE_PROOF_ERROR    = 100008
)

// RegisterHints registers all gnark/std hints for circuit compilation
var registerOnce sync.Once

// RegisterHints registers all required hints for the proving system
func RegisterHints() {
	registerOnce.Do(registerHints)
}

func registerHints() {
	solver.RegisterHint(bits.GetHints()...)            // Tiga circuit
	solver.RegisterHint(uints.GetHints()...)           // Fancaster circuit
	solver.RegisterHint(bitslice.GetHints()...)        // Fancaster circuit
	solver.RegisterHint(evmprecompiles.GetHints()...)  // Fancaster circuit
	solver.RegisterHint(tako_gnark_ecdsa.Pub2AddrHint) // Fancaster circuit
}

func init() {
	RegisterHints()
}

// loadAllCircuits loads all circuit templates from the template directory
func loadAllCircuits(templateDir string) (map[string]*CircuitData, error) {
	circuits := make(map[string]*CircuitData)
	dirs, err := ioutil.ReadDir(templateDir)
	if err != nil {
		return nil, err
	}

	for _, dir := range dirs {
		if dir.IsDir() {
			circuitId := dir.Name()
			log.Printf("Loading: %v", circuitId)
			circuitPath := filepath.Join(templateDir, circuitId)
			keysDir := filepath.Join(circuitPath, KeysFolderPath)

			// Load proving and verifying keys
			pk := groth16.NewProvingKey(ecc.BN254)
			pkFilePath := filepath.Join(keysDir, PkFileName)
			pkFile, err := os.Open(pkFilePath)
			if err != nil {
				log.Printf("Error opening pk.key for circuit %s: %v", circuitId, err)
				continue
			}
			_, err = pk.ReadFrom(pkFile)
			if err != nil {
				log.Printf("Error reading pk.key for circuit %s: %v", circuitId, err)
				continue
			}
			defer pkFile.Close()

			vk := groth16.NewVerifyingKey(ecc.BN254)
			vkFilePath := filepath.Join(keysDir, VkFileName)
			vkFile, err := os.Open(vkFilePath)
			if err != nil {
				log.Printf("Error opening vk.key for circuit %s: %v", circuitId, err)
				continue
			}
			defer vkFile.Close()
			if _, err := vk.ReadFrom(vkFile); err != nil {
				log.Printf("Error reading vk.key for circuit %s: %v", circuitId, err)
				continue
			}

			// Load ccs
			ccsFilePath := filepath.Join(circuitPath, R1csFileName)
			ccsFile, err := os.ReadFile(ccsFilePath)
			if err != nil {
				log.Printf("Error opening r1csFilePath for circuit %s: %v", circuitId, err)
				continue
			}
			ccsBuffer := bytes.NewBuffer(ccsFile)
			ccs := groth16.NewCS(ecc.BN254)
			_, err = ccs.ReadFrom(ccsBuffer)
			if err != nil {
				log.Printf("Error reading R1CS for circuit %s: %v", circuitId, err)
				continue
			}

			circuits[circuitId] = &CircuitData{
				Pk:  pk,
				Vk:  vk,
				Ccs: ccs,
				// NumOutput:   numOutput,
				// NumInPublic: numInPublic,
				CircuitPath: circuitPath,
			}
		}
	}
	return circuits, nil
}

type ZbFrCircuit struct {
	Leverage       frontend.Variable
	DeltaSpot      frontend.Variable
	DeltaPerpLong  frontend.Variable
	DeltaPerpShort frontend.Variable
	LeverageUpper  frontend.Variable `gnark:",public"`
	DeltaUpper     frontend.Variable `gnark:",public"`
	ProjectId      frontend.Variable `gnark:",public"`
}

type TigaCircuit struct {
	// timestamp var
	PreTimestamp     frontend.Variable
	CurrentTimestamp frontend.Variable
	NowTime          frontend.Variable

	// block height var
	PreHeight     frontend.Variable
	CurrentHeight frontend.Variable

	// block hash field var
	ParentHash frontend.Variable `gnark:",public"`
	PrevHash   frontend.Variable `gnark:",public"`

	// mix hash var
	MixHash frontend.Variable
	// uncle hash var
	UncleHash frontend.Variable

	// gas var
	GasLimit frontend.Variable
	GasUsed  frontend.Variable

	// nonce var
	Nonce frontend.Variable

	// diffculty var
	Difficulty frontend.Variable

	// ProjectId var
	ProjectId frontend.Variable `gnark:",public"`
}

type FancasterAnonymousCircuit struct {
	Message   emulated.Element[emulated.Secp256k1Fr]
	V         frontend.Variable
	R         emulated.Element[emulated.Secp256k1Fr]
	S         emulated.Element[emulated.Secp256k1Fr]
	Expected  sw_emulated.AffinePoint[emulated.Secp256k1Fp]
	RootHash  frontend.Variable
	Index     frontend.Variable
	Path      [MerklePathLength]frontend.Variable
	ProjectId frontend.Variable `gnark:",public"`
}

func (circuit *TigaCircuit) Define(api frontend.API) error {
	// Define the constraints for the TigaCircuit here
	return nil
}

func toStringMap(data map[string]interface{}) map[string]string {
	result := make(map[string]string)
	for k, v := range data {
		switch value := v.(type) {
		case json.Number: // Number type
			result[k] = value.String()
		case string: // Already a string
			result[k] = value
		default: // Other types, format as string
			result[k] = fmt.Sprintf("%v", value)
		}
	}
	return result
}

type FuturesCoinPosition struct {
	Symbol        string  `json:"symbol"`
	NotionalValue float64 `json:"notionalValue"`
	Leverage      string  `json:"leverage"`
}

type FuturesCoinAsset struct {
	Symbol        string  `json:"symbol"`
	WalletBalance float64 `json:"walletBalance"`
	MarginBalance float64 `json:"marginBalance"`
}

type FuturesPosition struct {
	Symbol      string  `json:"symbol"`
	PositionAmt float64 `json:"positionAmt"`
	Leverage    string  `json:"leverage"`
}

type SpotAsset struct {
	Asset string  `json:"asset"`
	Free  float64 `json:"free"`
}

type DataFile struct {
	FuturesCoinPositions []FuturesCoinPosition `json:"futures_coin_positions"`
	FuturesCoinAssets    []FuturesCoinAsset    `json:"futures_coin_assets"`
	FuturesPositions     []FuturesPosition     `json:"futures_positions"`
	SpotAssets           []SpotAsset           `json:"spot_assets"`
}

// Load function
func load(filename string) (*DataFile, error) {
	// Open JSON file
	file, err := os.Open(filename)
	if err != nil {
		return nil, fmt.Errorf("failed to open file: %w", err)
	}
	defer file.Close()

	// Read file content
	data, err := ioutil.ReadAll(file)
	if err != nil {
		return nil, fmt.Errorf("failed to read file: %w", err)
	}

	// Define struct instance
	var dataFile DataFile

	// Parse JSON data
	err = json.Unmarshal(data, &dataFile)
	if err != nil {
		return nil, fmt.Errorf("failed to parse JSON: %w", err)
	}

	return &dataFile, nil
}

func (circuit *ZbFrCircuit) Define(api frontend.API) error {
	return nil
}

func (s *server) ProveBinanceOffchain(ctx context.Context, in *pb.ProveRequest) (*pb.ProveResponseV2, error) {
	totalStart := time.Now()
	circuitId := in.GetTemp()
	circuitData, ok := s.circuits[circuitId]
	if !ok {
		return &pb.ProveResponseV2{
			Code: STATUS_CODE_UNSUPPORT_CIRCUIT,
			Msg:  fmt.Sprintf("Circuit [%s] not found", circuitId),
		}, nil
	}
	if len(in.GetInput()) > 1 {
		atomic.AddInt32(&s.runningProveTasks, 1)
		defer atomic.AddInt32(&s.runningProveTasks, -1)

		jsonParseStart := time.Now()

		// Read input data from input json file, e.g. 'BTC'
		asset := in.GetInput()
		// Coin-based corresponding symbol
		asset_coin_symbol := map[string]string{
			"BTC": "BTCUSD_PERP",
			"ETH": "ETHUSD_PERP",
		}

		data, err := load("multicoin_asset.json")
		if err != nil {
			log.Printf("Error loading JSON data: %v", err)
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_JSON_FROMAT_ERROR,
				Msg:  "Error loading JSON data",
			}, nil
		}

		log.Printf("JSON parsing took %v", time.Since(jsonParseStart))

		leverage := int64(1)
		perpLong := float64(0)
		perpShort := float64(0)
		for _, v := range data.FuturesCoinPositions {
			if v.Symbol == asset_coin_symbol[asset] {
				// v.Leverage bigger than leverage
				// Convert to int64
				vleverage, err := strconv.ParseInt(v.Leverage, 10, 64) // Base 10, 64-bit width
				if err != nil {
					fmt.Println("Format error:", err)
				}

				if vleverage > leverage {
					leverage = vleverage
				}
				if v.NotionalValue > 0 {
					perpLong = perpLong + v.NotionalValue*SatoshiMultiplier
				} else {
					perpShort = perpShort + v.NotionalValue*SatoshiMultiplier
				}
			}
		}

		walletBalance := float64(0)
		marginBalance := float64(0)
		for _, v := range data.FuturesCoinAssets {
			if v.Symbol == asset {
				walletBalance = walletBalance + v.WalletBalance*SatoshiMultiplier
				marginBalance = marginBalance + v.MarginBalance*SatoshiMultiplier
			}
		}

		witnessGenStart := time.Now()

		assignment := &ZbFrCircuit{
			Leverage:       leverage,
			DeltaSpot:      big.NewInt(int64(marginBalance)),
			DeltaPerpLong:  big.NewInt(int64(perpLong)),
			DeltaPerpShort: big.NewInt(int64(perpShort)),
			LeverageUpper:  MaxLeverage,
			DeltaUpper:     MaxDelta,
			ProjectId:      BinanceProjectID,
		}

		secretWitness, err := frontend.NewWitness(assignment, ecc.BN254.ScalarField())
		if err != nil {
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_TO_SECRET_WITNESS_ERROR,
				Msg:  "Error secretWitness",
			}, nil
		}
		rawPublicWitness, _ := secretWitness.Public()

		log.Printf("Generating witnesses took %v", time.Since(witnessGenStart))

		exportResultStart := time.Now()

		rawProof, err := groth16.Prove(circuitData.Ccs, circuitData.Pk, secretWitness, backend.WithIcicleAcceleration())
		if err != nil {
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_GENERATE_PROOF_ERROR,
				Msg:  "Error Prove",
			}, nil
		}
		log.Printf("Export result took %v", time.Since(exportResultStart))

		proofJson, err := json.Marshal(rawProof)
		if err != nil {
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_GENERATE_PROOF_ERROR,
				Msg:  "Error marshaling proof to json",
			}, nil
		}

		witnessJson, err := json.Marshal(rawPublicWitness.Vector().(fr.Vector))
		if err != nil {
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_GENERATE_PROOF_ERROR,
				Msg:  "Error witnessPublic",
			}, nil
		}

		proof := string(proofJson)

		var proofBuffer bytes.Buffer
		_, err = rawProof.WriteTo(&proofBuffer)
		if err != nil {
			log.Printf("Error serializing proof: %v", err)
			return &pb.ProveResponseV2{
				Code: -1,
				Msg:  "Error serializing proof to bytes",
			}, nil
		}
		proofBytes := proofBuffer.Bytes()

		rawProofSolidity := RunProveExportResult(rawProof, rawPublicWitness)

		proofSolidityJson, err := json.Marshal(rawProofSolidity)
		if err != nil {
			log.Printf("Error marshaling result to JSON: %v", err)
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_GENERATE_PROOF_ERROR,
				Msg:  "Failed to marshal solidity proof to JSON",
			}, nil
		}
		proofSolidity := string(proofSolidityJson)

		publicWitness := string(witnessJson)
		var publicWitnessBuffer bytes.Buffer
		_, err = rawPublicWitness.WriteTo(&publicWitnessBuffer)
		if err != nil {
			log.Printf("Error serializing witness: %v", err)
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_TO_PUBLIC_WITNESS_ERROR,
				Msg:  "Error serializing witness to bytes",
			}, nil
		}
		publicWitnessBytes := publicWitnessBuffer.Bytes()

		log.Printf("Total execution took %v", time.Since(totalStart))

		return &pb.ProveResponseV2{
			Code:               0,
			Msg:                "Successfully",
			Proof:              proof,
			ProofBytes:         proofBytes,
			ProofSolidity:      proofSolidity,
			PublicWitness:      publicWitness,
			PublicWitnessBytes: publicWitnessBytes,
		}, nil
	}
	return &pb.ProveResponseV2{
		Code: -1,
		Msg:  "Execution failed due to invalid input",
	}, nil

}

func (s *server) ProveTigaOffchain(ctx context.Context, in *pb.ProveRequest) (*pb.ProveResponseV2, error) {
	totalStart := time.Now()
	circuitId := in.GetTemp()
	circuitData, ok := s.circuits[circuitId]
	if !ok {
		return &pb.ProveResponseV2{
			Code: STATUS_CODE_UNSUPPORT_CIRCUIT,
			Msg:  fmt.Sprintf("Circuit [%s] not found", circuitId),
		}, nil
	}

	if len(in.GetInput()) > 1 {

		atomic.AddInt32(&s.runningProveTasks, 1)
		defer atomic.AddInt32(&s.runningProveTasks, -1)

		jsonParseStart := time.Now()

		decoder := json.NewDecoder(strings.NewReader(in.Input))
		decoder.UseNumber()

		var jsonData map[string]interface{}
		err := decoder.Decode(&jsonData)

		if err != nil {
			log.Printf("Error parsing JSON data: %v", err)
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_JSON_FROMAT_ERROR,
				Msg:  "Error parsing JSON data",
			}, nil
		}

		stringData := toStringMap(jsonData)

		log.Printf("JSON parsing took %v", time.Since(jsonParseStart))

		witnessGenStart := time.Now()

		assignment := &TigaCircuit{
			PreHeight:        stringData["PreHeight"],
			CurrentHeight:    stringData["CurrentHeight"],
			PreTimestamp:     stringData["PreTimestamp"],
			CurrentTimestamp: stringData["CurrentTimestamp"],
			NowTime:          stringData["NowTime"],
			ParentHash:       stringData["ParentHash"],
			PrevHash:         stringData["PrevHash"],
			UncleHash:        stringData["UncleHash"],
			MixHash:          stringData["MixHash"],
			GasLimit:         stringData["GasLimit"],
			GasUsed:          stringData["GasUsed"],
			Nonce:            stringData["nonce"],
			Difficulty:       stringData["difficulty"],
			ProjectId:        stringData["ProjectId"],
		}

		secretWitness, err := frontend.NewWitness(assignment, ecc.BN254.ScalarField())
		if err != nil {
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_TO_SECRET_WITNESS_ERROR,
				Msg:  "Error secretWitness",
			}, nil
		}
		rawPublicWitness, _ := secretWitness.Public()

		log.Printf("Generating witnesses took %v", time.Since(witnessGenStart))

		exportResultStart := time.Now()

		rawProof, err := groth16.Prove(circuitData.Ccs, circuitData.Pk, secretWitness, backend.WithIcicleAcceleration())
		if err != nil {
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_GENERATE_PROOF_ERROR,
				Msg:  "Error Prove",
			}, nil
		}
		log.Printf("Export result took %v", time.Since(exportResultStart))

		proofJson, err := json.Marshal(rawProof)
		if err != nil {
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_GENERATE_PROOF_ERROR,
				Msg:  "Error marshaling proof to json",
			}, nil
		}

		witnessJson, err := json.Marshal(rawPublicWitness.Vector().(fr.Vector))
		if err != nil {
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_GENERATE_PROOF_ERROR,
				Msg:  "Error witnessPublic",
			}, nil
		}

		proof := string(proofJson)

		var proofBuffer bytes.Buffer
		_, err = rawProof.WriteTo(&proofBuffer)
		if err != nil {
			log.Printf("Error serializing proof: %v", err)
			return &pb.ProveResponseV2{
				Code: -1,
				Msg:  "Error serializing proof to bytes",
			}, nil
		}
		proofBytes := proofBuffer.Bytes()

		rawProofSolidity := RunProveExportResult(rawProof, rawPublicWitness)

		proofSolidityJson, err := json.Marshal(rawProofSolidity)
		if err != nil {
			log.Printf("Error marshaling result to JSON: %v", err)
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_GENERATE_PROOF_ERROR,
				Msg:  "Failed to marshal solidity proof to JSON",
			}, nil
		}
		proofSolidity := string(proofSolidityJson)

		publicWitness := string(witnessJson)
		var publicWitnessBuffer bytes.Buffer
		_, err = rawPublicWitness.WriteTo(&publicWitnessBuffer)
		if err != nil {
			log.Printf("Error serializing witness: %v", err)
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_TO_PUBLIC_WITNESS_ERROR,
				Msg:  "Error serializing witness to bytes",
			}, nil
		}
		publicWitnessBytes := publicWitnessBuffer.Bytes()

		log.Printf("Total execution took %v", time.Since(totalStart))

		return &pb.ProveResponseV2{
			Code:               0,
			Msg:                "Successfully",
			Proof:              proof,
			ProofBytes:         proofBytes,
			ProofSolidity:      proofSolidity,
			PublicWitness:      publicWitness,
			PublicWitnessBytes: publicWitnessBytes,
		}, nil
	}
	return &pb.ProveResponseV2{
		Code: -1,
		Msg:  "Execution failed due to invalid input",
	}, nil
}

func (circuit *FancasterAnonymousCircuit) Define(api frontend.API) error {
	return nil
}

func (s *server) ProveMerkleOffchain(ctx context.Context, in *pb.ProveRequest) (*pb.ProveResponseV2, error) {
	totalStart := time.Now()
	circuitId := in.GetTemp()
	circuitData, ok := s.circuits[circuitId]
	if !ok {
		return &pb.ProveResponseV2{
			Code: STATUS_CODE_UNSUPPORT_CIRCUIT,
			Msg:  fmt.Sprintf("Circuit [%s] not found", circuitId),
		}, nil
	}

	if len(in.GetInput()) > 1 {
		atomic.AddInt32(&s.runningProveTasks, 1)
		defer atomic.AddInt32(&s.runningProveTasks, -1)

		jsonParseStart := time.Now()

		// ----------- deserialize --------------
		var raw FancasterAnonymousCircuitRaw
		err := json.Unmarshal([]byte(in.Input), &raw)
		if err != nil {
			log.Fatal("unmarshal error:", err)
		}

		assignment, err := Convert(raw)
		if err != nil {
			log.Fatal("convert error:", err)
		}

		log.Printf("JSON parsing took %v", time.Since(jsonParseStart))
		witnessGenStart := time.Now()
		secretWitness, err := frontend.NewWitness(&assignment, ecc.BN254.ScalarField())
		if err != nil {
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_TO_SECRET_WITNESS_ERROR,
				Msg:  "Error secretWitness",
			}, nil
		}
		rawPublicWitness, _ := secretWitness.Public()

		log.Printf("Generating witnesses took %v", time.Since(witnessGenStart))

		exportResultStart := time.Now()

		rawProof, err := groth16.Prove(circuitData.Ccs, circuitData.Pk, secretWitness, backend.WithIcicleAcceleration())
		if err != nil {
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_GENERATE_PROOF_ERROR,
				Msg:  "Error Prove",
			}, nil
		}
		log.Printf("Export result took %v", time.Since(exportResultStart))

		proofJson, err := json.Marshal(rawProof)
		if err != nil {
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_GENERATE_PROOF_ERROR,
				Msg:  "Error marshaling proof to json",
			}, nil
		}

		witnessJson, err := json.Marshal(rawPublicWitness.Vector().(fr.Vector))
		if err != nil {
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_GENERATE_PROOF_ERROR,
				Msg:  "Error witnessPublic",
			}, nil
		}

		proof := string(proofJson)

		var proofBuffer bytes.Buffer
		_, err = rawProof.WriteTo(&proofBuffer)
		if err != nil {
			log.Printf("Error serializing proof: %v", err)
			return &pb.ProveResponseV2{
				Code: -1,
				Msg:  "Error serializing proof to bytes",
			}, nil
		}
		proofBytes := proofBuffer.Bytes()

		rawProofSolidity := RunProveExportResult(rawProof, rawPublicWitness)

		proofSolidityJson, err := json.Marshal(rawProofSolidity)
		if err != nil {
			log.Printf("Error marshaling result to JSON: %v", err)
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_GENERATE_PROOF_ERROR,
				Msg:  "Failed to marshal solidity proof to JSON",
			}, nil
		}
		proofSolidity := string(proofSolidityJson)

		publicWitness := string(witnessJson)
		var publicWitnessBuffer bytes.Buffer
		_, err = rawPublicWitness.WriteTo(&publicWitnessBuffer)
		if err != nil {
			log.Printf("Error serializing witness: %v", err)
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_TO_PUBLIC_WITNESS_ERROR,
				Msg:  "Error serializing witness to bytes",
			}, nil
		}
		publicWitnessBytes := publicWitnessBuffer.Bytes()

		log.Printf("Total execution took %v", time.Since(totalStart))

		return &pb.ProveResponseV2{
			Code:               0,
			Msg:                "Successfully",
			Proof:              proof,
			ProofBytes:         proofBytes,
			ProofSolidity:      proofSolidity,
			PublicWitness:      publicWitness,
			PublicWitnessBytes: publicWitnessBytes,
		}, nil
	}
	return &pb.ProveResponseV2{
		Code: -1,
		Msg:  "Execution failed due to invalid input",
	}, nil
}

func (s *server) GetRunningProveTasks(ctx context.Context, in *pb.Empty) (*pb.GetRunningProveTasksResponse, error) {
	count := atomic.LoadInt32(&s.runningProveTasks) // Get current counter value
	return &pb.GetRunningProveTasksResponse{
		Code:  0,
		Msg:   "Execution failed due to invalid input",
		Count: count,
	}, nil
}

// Ping implements the health check endpoint
func (s *server) Ping(ctx context.Context, in *pb.Empty) (*pb.Empty, error) {
	log.Printf("Health check ping received")
	return &pb.Empty{}, nil
}

// healthCheckHandler handles HTTP health check requests
func healthCheckHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	response := map[string]string{
		"status":  "pong",
		"message": "Service is healthy",
		"version": Version,
	}
	json.NewEncoder(w).Encode(response)
}

func main() {
	port := flag.Int("p", DefaultPort, "The port on which the server will listen")
	httpPort := flag.Int("http", DefaultPort+1, "The HTTP port for health checks")
	templateFolderPath := flag.String("temp", "./template", "Circuits template folder path")
	flag.Parse()

	log.Printf("Prover is running, version: " + Version)

	loadCircuitsStart := time.Now()
	circuits, err := loadAllCircuits(*templateFolderPath)
	if err != nil {
		log.Printf("Failed to load circuits: %v", err)
	}
	log.Printf("load circuits took %v", time.Since(loadCircuitsStart))

	// Start HTTP server for health checks
	go func() {
		http.HandleFunc("/health", healthCheckHandler)
		http.HandleFunc("/ping", healthCheckHandler)
		log.Printf("HTTP health check server starting on port %v", *httpPort)
		if err := http.ListenAndServe(fmt.Sprintf(":%v", *httpPort), nil); err != nil {
			log.Printf("HTTP server failed: %v", err)
		}
	}()

	// Start gRPC server
	lis, err := net.Listen("tcp", fmt.Sprintf(":%v", *port))
	if err != nil {
		log.Printf("failed to listen: %v", err)
	}

	s := grpc.NewServer()
	log.Printf("Successfully, bind port: %v", *port)
	pb.RegisterProveServiceServer(s, &server{
		circuits: circuits, // Pass loaded circuits to server instance
	})

	if err := s.Serve(lis); err != nil {
		log.Printf("failed to serve: %v", err)
	}
}
