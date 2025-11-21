package main

import (
	"bufio"
	"bytes"
	pb "circom-prover/src/protobuf"
	"circom-prover/src/utils"
	"context"
	"encoding/base64"
	"encoding/json"
	"flag"
	"fmt"
	"io/ioutil"
	"log"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync/atomic"
	"time"

	"github.com/consensys/gnark-crypto/ecc"
	"github.com/consensys/gnark/backend"
	"github.com/consensys/gnark/backend/groth16"
	"github.com/consensys/gnark/constraint"
	"github.com/consensys/gnark/frontend"
	"github.com/google/uuid"
	icicleRunTime "github.com/ingonyama-zk/icicle-gnark/v3/wrappers/golang/runtime"
	"google.golang.org/grpc"
)

// CircuitData holds the data for a circuit template
type CircuitData struct {
	Pk          groth16.ProvingKey
	Vk          groth16.VerifyingKey
	Ccs         constraint.ConstraintSystem
	NumOutput   uint32
	NumInPublic uint32
	CircuitPath string
}

type DeviceInfo struct {
	*icicleRunTime.Device
	TaskCount int32
}

// server struct with circuits map to hold multiple circuit templates
type server struct {
	pb.UnimplementedProveServiceServer
	circuits          map[string]*CircuitData
	devices           map[int]*DeviceInfo
	runningProveTasks int32
}

const (
	Version = "v1.3.1"

	// File paths
	InputFolderPath = "input"
	WtnsFolderPath  = "wtns"
	KeysFolderPath  = "keys"

	// File names
	PkFileName              = "pk.key"
	VkFileName              = "vk.key"
	R1csFileName            = "circuit.r1cs"
	GenerateWitnessFilename = "generate_witness"
	DeviceType              = "CUDA"

	// Network configuration
	DefaultPort = 60051

	// Buffer configuration
	BufferSize = 1024 * 1024 // 1MB buffer for file reading

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

func loadDevice() (map[int]*DeviceInfo, error) {
	devices := make(map[int]*DeviceInfo)

	// Get current active device (for debugging)
	activeDevice, icicleErr := icicleRunTime.GetActiveDevice()
	if icicleErr != 0 {
		log.Printf("[loadDevice] Warning: Unable to get active device: %v", icicleErr)
	} else {
		log.Printf("[loadDevice] Active device is: %v", activeDevice.GetDeviceType())
	}

	// Get total device count
	deviceCount, icicleErr := icicleRunTime.GetDeviceCount()
	if icicleErr != 0 {
		return nil, fmt.Errorf("failed to get device count: %v", icicleErr)
	}

	log.Printf("[loadDevice] Total detected devices: %d", deviceCount)

	deviceNames, icicleErr := icicleRunTime.GetRegisteredDevices()
	if icicleErr != 0 {
		log.Fatalf("Failed to get registered devices: %v", icicleErr)
	}
	fmt.Printf("Registered devices: %v\n", deviceNames)

	// Iterate through all devices, check availability
	availableDeviceCount := 0
	for i := 0; i < deviceCount; i++ {
		device := icicleRunTime.CreateDevice(DeviceType, i)

		// Ensure device is available
		if !icicleRunTime.IsDeviceAvailable(&device) {
			log.Printf("[loadDevice] Warning: Device %d is not available, skipping...", i)
			continue
		}

		// Record available device
		devices[i] = &DeviceInfo{
			Device:    &device,
			TaskCount: 0,
		}
		availableDeviceCount++
	}

	// If no available devices found, return error
	if availableDeviceCount == 0 {
		return nil, fmt.Errorf("no available devices found")
	}

	log.Printf("[loadDevice] Successfully loaded %d available devices", availableDeviceCount)
	return devices, nil
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
			//r1csDir := filepath.Join(circuitPath, R1csFolderPath)

			// Load pk and vk
			pk := groth16.NewProvingKey(ecc.BN254)
			pkFilePath := filepath.Join(keysDir, PkFileName)
			pkFile, err := os.Open(pkFilePath)
			if err != nil {
				log.Printf("Error opening pk.key for circuit %s: %v", circuitId, err)
				continue
			}
			defer pkFile.Close()
			bufReader := bufio.NewReaderSize(pkFile, BufferSize)
			if _, err := pk.UnsafeReadFrom(bufReader); err != nil {
				log.Printf("Error reading pk.key for circuit %s: %v", circuitId, err)
				continue
			}

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
			r1csFilePath := filepath.Join(circuitPath, R1csFileName)
			ccs, numOutput, numInPublic, err := utils.ReadR1CS(r1csFilePath)
			if err != nil {
				log.Printf("Error reading R1CS for circuit %s: %v", circuitId, err)
				continue
			}

			circuits[circuitId] = &CircuitData{
				Pk:          pk,
				Vk:          vk,
				Ccs:         ccs,
				NumOutput:   numOutput,
				NumInPublic: numInPublic,
				CircuitPath: circuitPath,
			}
		}
	}
	return circuits, nil
}

func (s *server) getDevice() (*icicleRunTime.Device, int) {
	selectedIndex := -1
	var selectedDevice *icicleRunTime.Device
	minTasks := int32(1<<31 - 1) // Set a large initial value

	for i, devInfo := range s.devices {
		taskCount := atomic.LoadInt32(&devInfo.TaskCount) // Read task count
		if taskCount < minTasks {
			minTasks = taskCount
			selectedIndex = i
			selectedDevice = devInfo.Device
		}
	}

	return selectedDevice, selectedIndex
}

func (s *server) ProveV2(ctx context.Context, in *pb.ProveNosha256Request) (*pb.ProveResponseV2, error) {
	var err error
	totalStart := time.Now()
	circuitId := in.GetTemp()
	circuitData, ok := s.circuits[circuitId]
	if !ok {
		return &pb.ProveResponseV2{
			Code: STATUS_CODE_GPU_DEVICE_ERROR,
			Msg:  fmt.Sprintf("Circuit [%s] not found", circuitId),
		}, nil
	}

	device, deviceIndex := s.getDevice()
	if device == nil {
		return &pb.ProveResponseV2{
			Code: STATUS_CODE_UNSUPPORT_CIRCUIT, Msg: "No available devices",
		}, nil
	}

	if len(in.GetInput()) > 1 {

		atomic.AddInt32(&s.runningProveTasks, 1)
		defer atomic.AddInt32(&s.runningProveTasks, -1)
		atomic.AddInt32(&s.devices[deviceIndex].TaskCount, 1)
		defer atomic.AddInt32(&s.devices[deviceIndex].TaskCount, -1)

		jsonParseStart := time.Now()

		var jsonData map[string]interface{}
		err = json.Unmarshal([]byte(in.Input), &jsonData)
		if err != nil {
			log.Printf("Error parsing JSON data: %v", err)
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_JSON_FROMAT_ERROR,
				Msg:  "Error parsing JSON data",
			}, nil
		}

		log.Printf("JSON parsing took %v", time.Since(jsonParseStart))

		jwtProcessStart := time.Now()

		jwtSegments, ok := jsonData["jwt_segments"].([]interface{})
		if !ok {
			log.Printf("jwt_segments is not of type []interface{} or is nil")
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_INVALID_INPUT,
				Msg:  "Invalid data format for jwt_segments",
			}, nil
		}

		var jwtSegmentsStr [][]string
		for _, seg := range jwtSegments {
			var segment []string
			for _, v := range seg.([]interface{}) {
				segment = append(segment, v.(string))
			}
			jwtSegmentsStr = append(jwtSegmentsStr, segment)
		}

		if circuitId == "10007" || circuitId == "10008" {

			jwt, err := utils.ReconstructJWTFromSegments(jwtSegmentsStr)
			if err != nil || jwt == "" {
				log.Printf("Error reconstructing JWT: %v", err)
				return &pb.ProveResponseV2{
					Code: STATUS_CODE_INVALID_INPUT,
					Msg:  "Invalid data format for jwt_segments",
				}, nil
			}
			parts := strings.Split(jwt, ".")
			payloadBytes, err := base64.RawURLEncoding.DecodeString(parts[1])
			if err != nil {
				log.Printf("Error decoding JWT: %v", err)
				return &pb.ProveResponseV2{
					Code: STATUS_CODE_INVALID_INPUT,
					Msg:  "Invalid data format for jwt_segments",
				}, nil
			}
			var jwtClaims map[string]interface{}
			if err := json.Unmarshal(payloadBytes, &jwtClaims); err != nil {
				log.Printf("Error parsing JSON data: %v", err)
				return &pb.ProveResponseV2{
					Code: STATUS_CODE_JSON_FROMAT_ERROR,
					Msg:  "Error parsing JSON data",
				}, nil
			}
			iss, ok := jwtClaims["iss"].(string)
			if !ok {
				log.Printf("iss is not of type string or is nil")
				return &pb.ProveResponseV2{
					Code: STATUS_CODE_INVALID_INPUT,
					Msg:  "Invalid data format for jwt_segments",
				}, nil
			}
			aud, ok := jwtClaims["aud"].(string)
			if !ok {
				log.Printf("aud is not of type string or is nil")
				return &pb.ProveResponseV2{
					Code: STATUS_CODE_INVALID_INPUT,
					Msg:  "Invalid data format for jwt_segments",
				}, nil
			}

			if iss != "https://securetoken.google.com/sollpayapp" || aud != "sollpayapp" {
				log.Printf("iss or aud is incorrect")
				return &pb.ProveResponseV2{
					Code: STATUS_CODE_INVALID_INPUT,
					Msg:  "Invalid data format for jwt_segments",
				}, nil
			}
		}

		jwtSha256, ok := jsonData["jwt_sha256"].([]interface{})
		if !ok {
			log.Printf("jwt_sha256 is not of type []interface{} or is nil")
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_INVALID_INPUT,
				Msg:  "Invalid data format for jwt_sha256",
			}, nil
		}

		log.Printf("Processing jwt_segments and jwt_sha256 took %v", time.Since(jwtProcessStart))

		shaCheckStart := time.Now()

		jwtSha256String := utils.ConvertToBinaryString(jwtSha256)

		jwtPaddedRestored := utils.MergeJWT(jwtSegmentsStr)
		jwtSegmentSha256 := utils.Uint8ToBits(utils.ShaHash(jwtPaddedRestored[:in.GetLength()]))

		// Verify both are equal to ensure message integrity
		if jwtSegmentSha256 != jwtSha256String {
			fmt.Println("SHA256 did not match.")
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_SHA256_NOT_MATCH,
				Msg:  "SHA256 did not match",
			}, nil
		}

		log.Printf("SHA256 verification took %v", time.Since(shaCheckStart))

		saveJSONStart := time.Now()

		id := uuid.New().String()
		jsonFilename := utils.GenerateUniqueFilename("input", "json", id)
		jsonFilePath := filepath.Join(circuitData.CircuitPath, InputFolderPath)
		jsonFilePath = filepath.Join(jsonFilePath, jsonFilename)
		err = ioutil.WriteFile(jsonFilePath, []byte(in.Input), 0644)
		if err != nil {
			log.Printf("Error saving input as JSON: %v", err)
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_JSON_FROMAT_ERROR,
				Msg:  "Execution failed: could not save input as JSON",
			}, nil
		}

		log.Printf("Saving input as JSON took %v", time.Since(saveJSONStart))

		generateWtnsStart := time.Now()

		generateWitnessPath := filepath.Join(circuitData.CircuitPath, GenerateWitnessFilename)

		wtnsFileName := utils.GenerateUniqueFilename("output", "wtns", id)
		wtnsPath := filepath.Join(circuitData.CircuitPath, WtnsFolderPath)
		wtnsPath = filepath.Join(wtnsPath, wtnsFileName)

		cmd := exec.Command(generateWitnessPath, jsonFilePath, wtnsPath)
		if err := cmd.Run(); err != nil {
			log.Printf("Error running command: %v", err)
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_TO_WITNESS_ERROR,
				Msg:  "Execution failed: could not generate witness",
			}, nil
		}

		log.Printf("Running external command took %v", time.Since(generateWtnsStart))

		parseWitnessStart := time.Now()

		var w utils.R1CSCircuit
		w.Witness, w.WitnessPublic, err = utils.ParseWtns(wtnsPath, circuitData.NumOutput, circuitData.NumInPublic)
		if err != nil {

			return &pb.ProveResponseV2{
				Code: STATUS_CODE_TO_WITNESS_ERROR,
				Msg:  "Error Parse wtns",
			}, nil
		}

		log.Printf("Parsing witness file took %v", time.Since(parseWitnessStart))

		secretWitness, err := frontend.NewWitness(&w, ecc.BN254.ScalarField())
		if err != nil {

			return &pb.ProveResponseV2{
				Code: STATUS_CODE_TO_SECRET_WITNESS_ERROR,
				Msg:  "Error secretWitness",
			}, nil
		}
		rawPublicWitness, err := frontend.NewWitness(&w, ecc.BN254.ScalarField(), frontend.PublicOnly())
		if err != nil {
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_TO_PUBLIC_WITNESS_ERROR,
				Msg:  "Error Public Witness",
			}, nil
		}

		rawProof, err := groth16.Prove(circuitData.Ccs, circuitData.Pk, secretWitness, backend.WithIcicleAcceleration())
		if err != nil {
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_GENERATE_PROOF_ERROR,
				Msg:  "Error Prove",
			}, nil
		}

		proofJson, err := json.Marshal(rawProof)
		if err != nil {
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_GENERATE_PROOF_ERROR,
				Msg:  "Error marshaling proof to json",
			}, nil
		}

		witnessJson, err := json.Marshal(w.WitnessPublic)
		if err != nil {
			return &pb.ProveResponseV2{
				Code: STATUS_CODE_GENERATE_PROOF_ERROR,
				Msg:  "Witness public marshal error",
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
		rawProofSolidity := utils.RunProveExportResult(rawProof, rawPublicWitness)

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

func (s *server) ProveNosha256(ctx context.Context, in *pb.ProveNosha256Request) (*pb.ProveNosha256Response, error) {
	var err error
	totalStart := time.Now()
	circuitId := in.GetTemp()
	circuitData, ok := s.circuits[circuitId]
	if !ok {
		return &pb.ProveNosha256Response{
			Code: STATUS_CODE_GPU_DEVICE_ERROR,
			Msg:  fmt.Sprintf("Circuit [%s] not found", circuitId),
		}, nil
	}

	device, deviceIndex := s.getDevice()
	if device == nil {
		return &pb.ProveNosha256Response{
			Code: STATUS_CODE_UNSUPPORT_CIRCUIT,
			Msg:  "No available devices",
		}, nil
	}

	if len(in.GetInput()) > 1 {

		atomic.AddInt32(&s.runningProveTasks, 1)
		defer atomic.AddInt32(&s.runningProveTasks, -1)
		atomic.AddInt32(&s.devices[deviceIndex].TaskCount, 1)
		defer atomic.AddInt32(&s.devices[deviceIndex].TaskCount, -1)

		jsonParseStart := time.Now()

		var jsonData map[string]interface{}
		err = json.Unmarshal([]byte(in.Input), &jsonData)
		if err != nil {
			log.Printf("Error parsing JSON data: %v", err)
			return &pb.ProveNosha256Response{
				Code: STATUS_CODE_JSON_FROMAT_ERROR,
				Msg:  "Error parsing JSON data",
			}, nil
		}

		log.Printf("JSON parsing took %v", time.Since(jsonParseStart))

		jwtProcessStart := time.Now()

		jwtSegments, ok := jsonData["jwt_segments"].([]interface{})
		if !ok {
			log.Printf("jwt_segments is not of type []interface{} or is nil")
			return &pb.ProveNosha256Response{
				Code: STATUS_CODE_INVALID_INPUT,
				Msg:  "Invalid data format for jwt_segments",
			}, nil
		}

		var jwtSegmentsStr [][]string
		for _, seg := range jwtSegments {
			var segment []string
			for _, v := range seg.([]interface{}) {
				segment = append(segment, v.(string))
			}
			jwtSegmentsStr = append(jwtSegmentsStr, segment)
		}

		jwtSha256, ok := jsonData["jwt_sha256"].([]interface{})
		if !ok {
			log.Printf("jwt_sha256 is not of type []interface{} or is nil")
			return &pb.ProveNosha256Response{
				Code: STATUS_CODE_INVALID_INPUT,
				Msg:  "Invalid data format for jwt_sha256",
			}, nil
		}

		log.Printf("Processing jwt_segments and jwt_sha256 took %v", time.Since(jwtProcessStart))

		shaCheckStart := time.Now()

		jwtSha256String := utils.ConvertToBinaryString(jwtSha256)

		jwtPaddedRestored := utils.MergeJWT(jwtSegmentsStr)
		jwtSegmentSha256 := utils.Uint8ToBits(utils.ShaHash(jwtPaddedRestored[:in.GetLength()]))

		// Verify both are equal to ensure message integrity
		if jwtSegmentSha256 != jwtSha256String {
			fmt.Println("SHA256 did not match.")
			return &pb.ProveNosha256Response{
				Code: STATUS_CODE_SHA256_NOT_MATCH,
				Msg:  "SHA256 did not match",
			}, nil
		}

		log.Printf("SHA256 verification took %v", time.Since(shaCheckStart))

		saveJSONStart := time.Now()

		id := uuid.New().String()
		jsonFilename := utils.GenerateUniqueFilename("input", "json", id)
		jsonFilePath := filepath.Join(circuitData.CircuitPath, InputFolderPath)
		jsonFilePath = filepath.Join(jsonFilePath, jsonFilename)
		err = ioutil.WriteFile(jsonFilePath, []byte(in.Input), 0644)
		if err != nil {
			log.Printf("Error saving input as JSON: %v", err)
			return &pb.ProveNosha256Response{
				Code: STATUS_CODE_JSON_FROMAT_ERROR,
				Msg:  "Execution failed: could not save input as JSON",
			}, nil
		}

		log.Printf("Saving input as JSON took %v", time.Since(saveJSONStart))

		generateWtnsStart := time.Now()

		generateWitnessPath := filepath.Join(circuitData.CircuitPath, GenerateWitnessFilename)

		wtnsFileName := utils.GenerateUniqueFilename("output", "wtns", id)
		wtnsPath := filepath.Join(circuitData.CircuitPath, WtnsFolderPath)
		wtnsPath = filepath.Join(wtnsPath, wtnsFileName)

		cmd := exec.Command(generateWitnessPath, jsonFilePath, wtnsPath)
		if err := cmd.Run(); err != nil {
			log.Printf("Error running command: %v", err)
			return &pb.ProveNosha256Response{
				Code: STATUS_CODE_TO_WITNESS_ERROR,
				Msg:  "Execution failed: could not generate witness",
			}, nil
		}

		log.Printf("Running external command took %v", time.Since(generateWtnsStart))

		parseWitnessStart := time.Now()

		var w utils.R1CSCircuit
		w.Witness, w.WitnessPublic, err = utils.ParseWtns(wtnsPath, circuitData.NumOutput, circuitData.NumInPublic)
		if err != nil {

			return &pb.ProveNosha256Response{
				Code: STATUS_CODE_TO_WITNESS_ERROR,
				Msg:  "Error Parse wtns",
			}, nil
		}

		log.Printf("Parsing witness file took %v", time.Since(parseWitnessStart))

		witnessGenStart := time.Now()

		secretWitness, err := frontend.NewWitness(&w, ecc.BN254.ScalarField())
		if err != nil {

			return &pb.ProveNosha256Response{
				Code: STATUS_CODE_TO_SECRET_WITNESS_ERROR,
				Msg:  "Error secretWitness",
			}, nil
		}
		publicWitness, err := frontend.NewWitness(&w, ecc.BN254.ScalarField(), frontend.PublicOnly())
		if err != nil {
			return &pb.ProveNosha256Response{
				Code: STATUS_CODE_TO_PUBLIC_WITNESS_ERROR,
				Msg:  "Error Public Witness",
			}, nil
		}

		rawProof, err := groth16.Prove(circuitData.Ccs, circuitData.Pk, secretWitness, backend.WithIcicleAcceleration())
		if err != nil {
			return &pb.ProveNosha256Response{
				Code: STATUS_CODE_GENERATE_PROOF_ERROR,
				Msg:  "Error Prove",
			}, nil
		}

		rawProofSolidity := utils.RunProveExportResult(rawProof, publicWitness)

		proofSolidityJson, err := json.Marshal(rawProofSolidity)
		if err != nil {
			log.Printf("Error marshaling result to JSON: %v", err)
			return &pb.ProveNosha256Response{
				Code: STATUS_CODE_GENERATE_PROOF_ERROR,
				Msg:  "Failed to marshal solidity proof to JSON",
			}, nil
		}
		proofSolidity := string(proofSolidityJson)

		log.Printf("Total execution took %v", time.Since(totalStart))

		log.Printf("Generating witnesses took %v", time.Since(witnessGenStart))

		return &pb.ProveNosha256Response{
			Code:  0,
			Msg:   "Successfully",
			Proof: proofSolidity,
		}, nil
	}
	return &pb.ProveNosha256Response{
		Code: -1,
		Msg:  "Execution failed due to invalid input",
	}, nil
}

func (s *server) ProveNosha256Offchain(ctx context.Context, in *pb.ProveNosha256Request) (*pb.ProveNosha256OffchainResponse, error) {
	var err error
	totalStart := time.Now()
	circuitId := in.GetTemp()
	circuitData, ok := s.circuits[circuitId]
	if !ok {
		return &pb.ProveNosha256OffchainResponse{
			Code: STATUS_CODE_UNSUPPORT_CIRCUIT,
			Msg:  fmt.Sprintf("Circuit [%s] not found", circuitId),
		}, nil
	}

	device, deviceIndex := s.getDevice()
	if device == nil {
		return &pb.ProveNosha256OffchainResponse{
			Code: STATUS_CODE_GPU_DEVICE_ERROR,
			Msg:  "No available devices",
		}, nil
	}

	if len(in.GetInput()) > 1 {

		atomic.AddInt32(&s.runningProveTasks, 1)
		defer atomic.AddInt32(&s.runningProveTasks, -1)
		atomic.AddInt32(&s.devices[deviceIndex].TaskCount, 1)
		defer atomic.AddInt32(&s.devices[deviceIndex].TaskCount, -1)

		jsonParseStart := time.Now()

		var jsonData map[string]interface{}
		err = json.Unmarshal([]byte(in.Input), &jsonData)
		if err != nil {
			log.Printf("Error parsing JSON data: %v", err)
			return &pb.ProveNosha256OffchainResponse{
				Code: STATUS_CODE_JSON_FROMAT_ERROR,
				Msg:  "Error parsing JSON data",
			}, nil
		}

		log.Printf("JSON parsing took %v", time.Since(jsonParseStart))

		jwtProcessStart := time.Now()

		jwtSegments, ok := jsonData["jwt_segments"].([]interface{})
		if !ok {
			log.Printf("jwt_segments is not of type []interface{} or is nil")
			return &pb.ProveNosha256OffchainResponse{
				Code: STATUS_CODE_INVALID_INPUT,
				Msg:  "Invalid data format for jwt_segments",
			}, nil
		}

		var jwtSegmentsStr [][]string
		for _, seg := range jwtSegments {
			var segment []string
			for _, v := range seg.([]interface{}) {
				segment = append(segment, v.(string))
			}
			jwtSegmentsStr = append(jwtSegmentsStr, segment)
		}

		if circuitId == "10007" || circuitId == "10008" {

			jwt, err := utils.ReconstructJWTFromSegments(jwtSegmentsStr)
			if err != nil || jwt == "" {
				log.Printf("Error reconstructing JWT: %v", err)
				return &pb.ProveNosha256OffchainResponse{
					Code: STATUS_CODE_INVALID_INPUT,
					Msg:  "Invalid data format for jwt_segments",
				}, nil
			}
			parts := strings.Split(jwt, ".")
			payloadBytes, err := base64.RawURLEncoding.DecodeString(parts[1])
			if err != nil {
				log.Printf("Error decoding JWT: %v", err)
				return &pb.ProveNosha256OffchainResponse{
					Code: STATUS_CODE_INVALID_INPUT,
					Msg:  "Invalid data format for jwt_segments",
				}, nil
			}
			var jwtClaims map[string]interface{}
			if err := json.Unmarshal(payloadBytes, &jwtClaims); err != nil {
				log.Printf("Error parsing JSON data: %v", err)
				return &pb.ProveNosha256OffchainResponse{
					Code: STATUS_CODE_JSON_FROMAT_ERROR,
					Msg:  "Error parsing JSON data",
				}, nil
			}
			iss, ok := jwtClaims["iss"].(string)
			if !ok {
				log.Printf("iss is not of type string or is nil")
				return &pb.ProveNosha256OffchainResponse{
					Code: STATUS_CODE_INVALID_INPUT,
					Msg:  "Invalid data format for jwt_segments",
				}, nil
			}
			aud, ok := jwtClaims["aud"].(string)
			if !ok {
				log.Printf("aud is not of type string or is nil")
				return &pb.ProveNosha256OffchainResponse{
					Code: STATUS_CODE_INVALID_INPUT,
					Msg:  "Invalid data format for jwt_segments",
				}, nil
			}

			if iss != "https://securetoken.google.com/sollpayapp" || aud != "sollpayapp" {
				log.Printf("iss or aud is incorrect")
				return &pb.ProveNosha256OffchainResponse{
					Code: STATUS_CODE_INVALID_INPUT,
					Msg:  "Invalid data format for jwt_segments",
				}, nil
			}
		}

		jwtSha256, ok := jsonData["jwt_sha256"].([]interface{})
		if !ok {
			log.Printf("jwt_sha256 is not of type []interface{} or is nil")
			return &pb.ProveNosha256OffchainResponse{
				Code: STATUS_CODE_INVALID_INPUT,
				Msg:  "Invalid data format for jwt_sha256",
			}, nil
		}
		log.Printf("Processing jwt_segments and jwt_sha256 took %v", time.Since(jwtProcessStart))

		shaCheckStart := time.Now()

		jwtSha256String := utils.ConvertToBinaryString(jwtSha256)

		jwtPaddedRestored := utils.MergeJWT(jwtSegmentsStr)
		jwtSegmentSha256 := utils.Uint8ToBits(utils.ShaHash(jwtPaddedRestored[:in.GetLength()]))

		// Verify both are equal to ensure message integrity
		if jwtSegmentSha256 != jwtSha256String {
			fmt.Println("SHA256 did not match.")
			return &pb.ProveNosha256OffchainResponse{
				Code: STATUS_CODE_SHA256_NOT_MATCH,
				Msg:  "SHA256 did not match",
			}, nil
		}

		log.Printf("SHA256 verification took %v", time.Since(shaCheckStart))

		saveJSONStart := time.Now()

		id := uuid.New().String()
		jsonFilename := utils.GenerateUniqueFilename("input", "json", id)
		jsonFilePath := filepath.Join(circuitData.CircuitPath, InputFolderPath)
		jsonFilePath = filepath.Join(jsonFilePath, jsonFilename)
		err = ioutil.WriteFile(jsonFilePath, []byte(in.Input), 0644)
		if err != nil {
			log.Printf("Error saving input as JSON: %v", err)
			return &pb.ProveNosha256OffchainResponse{
				Code:    -1,
				Msg:     "Execution failed: could not save input as JSON",
				Proof:   nil,
				Witness: "",
			}, nil
		}

		log.Printf("Saving input as JSON took %v", time.Since(saveJSONStart))

		generateWtnsStart := time.Now()

		generateWitnessPath := filepath.Join(circuitData.CircuitPath, GenerateWitnessFilename)

		wtnsFileName := utils.GenerateUniqueFilename("output", "wtns", id)
		wtnsPath := filepath.Join(circuitData.CircuitPath, WtnsFolderPath)
		wtnsPath = filepath.Join(wtnsPath, wtnsFileName)

		cmd := exec.Command(generateWitnessPath, jsonFilePath, wtnsPath)
		if err := cmd.Run(); err != nil {
			log.Printf("Error running command: %v", err)
			return &pb.ProveNosha256OffchainResponse{
				Code: STATUS_CODE_TO_WITNESS_ERROR,
				Msg:  "Execution failed: could not generate witness",
			}, nil
		}

		log.Printf("Running external command took %v", time.Since(generateWtnsStart))

		parseWitnessStart := time.Now()

		var w utils.R1CSCircuit
		w.Witness, w.WitnessPublic, err = utils.ParseWtns(wtnsPath, circuitData.NumOutput, circuitData.NumInPublic)
		if err != nil {

			return &pb.ProveNosha256OffchainResponse{
				Code: STATUS_CODE_TO_WITNESS_ERROR,
				Msg:  "Error Parse wtns",
			}, nil
		}

		log.Printf("Parsing witness file took %v", time.Since(parseWitnessStart))

		witnessGenStart := time.Now()

		secretWitness, err := frontend.NewWitness(&w, ecc.BN254.ScalarField())
		if err != nil {

			return &pb.ProveNosha256OffchainResponse{
				Code: STATUS_CODE_TO_SECRET_WITNESS_ERROR,
				Msg:  "Error secretWitness",
			}, nil
		}

		log.Printf("Generating witnesses took %v", time.Since(witnessGenStart))

		proof, err := groth16.Prove(circuitData.Ccs, circuitData.Pk, secretWitness, backend.WithIcicleAcceleration())
		if err != nil {
			return &pb.ProveNosha256OffchainResponse{
				Code: STATUS_CODE_GENERATE_PROOF_ERROR,
				Msg:  "Error Prove",
			}, nil
		}

		exportResultStart := time.Now()

		var proofBuffer bytes.Buffer
		_, err = proof.WriteTo(&proofBuffer)
		if err != nil {
			log.Printf("Error serializing proof: %v", err)
			return &pb.ProveNosha256OffchainResponse{
				Code: STATUS_CODE_GENERATE_PROOF_ERROR,
				Msg:  "Error serializing proof",
			}, nil
		}
		proofBytes := proofBuffer.Bytes()

		log.Printf("Export result took %v", time.Since(exportResultStart))

		witnessPublicJsonData, err := json.Marshal(w.WitnessPublic)
		if err != nil {

			return &pb.ProveNosha256OffchainResponse{
				Code: STATUS_CODE_GENERATE_PROOF_ERROR,
				Msg:  "Error witnessPublic",
			}, nil
		}

		witnessPublicString := string(witnessPublicJsonData)

		log.Printf("Total execution took %v", time.Since(totalStart))

		return &pb.ProveNosha256OffchainResponse{
			Code:    0,
			Msg:     "Successfully",
			Witness: witnessPublicString,
			Proof:   proofBytes,
		}, nil
	}
	return &pb.ProveNosha256OffchainResponse{
		Code:    -1,
		Msg:     "Execution failed due to invalid input",
		Proof:   nil,
		Witness: "",
	}, nil
}

func (s *server) ProveNosha256WithWitness(ctx context.Context, in *pb.ProveNosha256Request) (*pb.ProveNosha256WithWitnessResponse, error) {
	var err error
	totalStart := time.Now()

	circuitId := in.GetTemp()
	circuitData, ok := s.circuits[circuitId]
	if !ok {
		return &pb.ProveNosha256WithWitnessResponse{
			Code:    -1,
			Msg:     fmt.Sprintf("Circuit [%s] not found", circuitId),
			Proof:   "",
			Witness: "",
		}, nil
	}

	if len(in.GetInput()) > 1 {
		atomic.AddInt32(&s.runningProveTasks, 1)
		defer atomic.AddInt32(&s.runningProveTasks, -1)
		jsonParseStart := time.Now()

		var jsonData map[string]interface{}
		err = json.Unmarshal([]byte(in.Input), &jsonData)
		if err != nil {
			log.Printf("Error parsing JSON data: %v", err)
			return &pb.ProveNosha256WithWitnessResponse{
				Code:    -1,
				Msg:     "Error parsing JSON data",
				Proof:   "",
				Witness: "",
			}, nil
		}

		log.Printf("JSON parsing took %v", time.Since(jsonParseStart))

		jwtProcessStart := time.Now()

		jwtSegments, ok := jsonData["jwt_segments"].([]interface{})
		if !ok {
			log.Printf("jwt_segments is not of type []interface{} or is nil")
			return &pb.ProveNosha256WithWitnessResponse{
				Code:    -1,
				Msg:     "Invalid data format for jwt_segments",
				Proof:   "",
				Witness: "",
			}, nil
		}

		var jwtSegmentsStr [][]string
		for _, seg := range jwtSegments {
			var segment []string
			for _, v := range seg.([]interface{}) {
				segment = append(segment, v.(string))
			}
			jwtSegmentsStr = append(jwtSegmentsStr, segment)
		}

		jwtSha256, ok := jsonData["jwt_sha256"].([]interface{})
		if !ok {
			log.Printf("jwt_sha256 is not of type []interface{} or is nil")
			return &pb.ProveNosha256WithWitnessResponse{
				Code:    -1,
				Msg:     "Invalid data format for jwt_sha256",
				Proof:   "",
				Witness: "",
			}, nil
		}

		log.Printf("Processing jwt_segments and jwt_sha256 took %v", time.Since(jwtProcessStart))

		shaCheckStart := time.Now()

		jwtSha256String := utils.ConvertToBinaryString(jwtSha256)

		jwtPaddedRestored := utils.MergeJWT(jwtSegmentsStr)
		jwtSegmentSha256 := utils.Uint8ToBits(utils.ShaHash(jwtPaddedRestored[:in.GetLength()]))

		// Verify both are equal to ensure message integrity
		if jwtSegmentSha256 != jwtSha256String {
			fmt.Println("SHA256 did not match.")
			return &pb.ProveNosha256WithWitnessResponse{
				Code:    -1,
				Msg:     "SHA256 did not match",
				Proof:   "",
				Witness: "",
			}, nil
		}

		log.Printf("SHA256 verification took %v", time.Since(shaCheckStart))

		saveJSONStart := time.Now()

		id := uuid.New().String()

		jsonFilename := utils.GenerateUniqueFilename("input", "json", id)
		jsonFilePath := filepath.Join(circuitData.CircuitPath, InputFolderPath)
		jsonFilePath = filepath.Join(jsonFilePath, jsonFilename)

		err = ioutil.WriteFile(jsonFilePath, []byte(in.Input), 0644)
		if err != nil {
			log.Printf("Error saving input as JSON: %v", err)
			return &pb.ProveNosha256WithWitnessResponse{
				Code:    -1,
				Msg:     "Execution failed: could not save input as JSON",
				Proof:   "",
				Witness: "",
			}, nil
		}

		log.Printf("Saving input as JSON took %v", time.Since(saveJSONStart))

		generateWtnsStart := time.Now()

		generateWitnessPath := filepath.Join(circuitData.CircuitPath, GenerateWitnessFilename)

		wtnsFileName := utils.GenerateUniqueFilename("output", "wtns", id)

		wtnsPath := filepath.Join(circuitData.CircuitPath, WtnsFolderPath)
		wtnsPath = filepath.Join(wtnsPath, wtnsFileName)
		cmd := exec.Command(generateWitnessPath, jsonFilePath, wtnsPath)
		if err := cmd.Run(); err != nil {
			log.Printf("Error running command: %v", err)
			return &pb.ProveNosha256WithWitnessResponse{
				Code:    -1,
				Msg:     "Execution failed: could not generate witness",
				Proof:   "",
				Witness: "",
			}, nil
		}

		log.Printf("Running external command took %v", time.Since(generateWtnsStart))

		parseWitnessStart := time.Now()

		var w utils.R1CSCircuit
		w.Witness, w.WitnessPublic, err = utils.ParseWtns(wtnsPath, circuitData.NumOutput, circuitData.NumInPublic)
		if err != nil {

			return &pb.ProveNosha256WithWitnessResponse{
				Code:    -1,
				Msg:     "Error Parse wtns",
				Proof:   "",
				Witness: "",
			}, nil
		}

		log.Printf("Parsing witness file took %v", time.Since(parseWitnessStart))

		witnessGenStart := time.Now()

		secretWitness, err := frontend.NewWitness(&w, ecc.BN254.ScalarField())
		if err != nil {

			return &pb.ProveNosha256WithWitnessResponse{
				Code:    -1,
				Msg:     "Error New Witness",
				Proof:   "",
				Witness: "",
			}, nil
		}

		log.Printf("Generating witnesses took %v", time.Since(witnessGenStart))

		proof, err := groth16.Prove(circuitData.Ccs, circuitData.Pk, secretWitness, backend.WithIcicleAcceleration())
		if err != nil {

			return &pb.ProveNosha256WithWitnessResponse{
				Code:    -1,
				Msg:     "Error Prove",
				Proof:   "",
				Witness: "",
			}, nil
		}

		proofJsonData, err := json.Marshal(proof)
		if err != nil {

			return &pb.ProveNosha256WithWitnessResponse{
				Code:    -1,
				Msg:     "Error proofJsonData",
				Witness: "",
				Proof:   "",
			}, nil
		}

		witnessPublicJsonData, err := json.Marshal(w.WitnessPublic)
		if err != nil {

			return &pb.ProveNosha256WithWitnessResponse{
				Code:    -1,
				Msg:     "Error witnessPublicJsonData",
				Witness: "",
				Proof:   "",
			}, nil
		}
		proofString := string(proofJsonData)
		witnessPublicString := string(witnessPublicJsonData)

		log.Printf("Total execution took %v", time.Since(totalStart))

		return &pb.ProveNosha256WithWitnessResponse{
			Code:    0,
			Msg:     "Successfully",
			Proof:   proofString,
			Witness: witnessPublicString,
		}, nil
	}
	return &pb.ProveNosha256WithWitnessResponse{
		Code:    -1,
		Msg:     "Execution failed due to invalid input",
		Proof:   "",
		Witness: "",
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

func (s *server) Ping(ctx context.Context, in *pb.Empty) (*pb.PingResponse, error) {
	return &pb.PingResponse{
		Code:      0,
		Msg:       "Server is running",
		Version:   Version,
		Timestamp: time.Now().Unix(),
	}, nil
}

func main() {
	port := flag.Int("p", DefaultPort, "The port on which the server will listen")
	templateFolderPath := flag.String("temp", "./template", "Circuits template folder path")
	flag.Parse()

	log.Printf("Prover is running, version: " + Version)

	loadCircuitsStart := time.Now()
	circuits, err := loadAllCircuits(*templateFolderPath)
	if err != nil {
		log.Printf("Failed to load circuits: %v", err)
	}
	log.Printf("load circuits took %v", time.Since(loadCircuitsStart))

	lis, err := net.Listen("tcp", fmt.Sprintf(":%v", *port))
	if err != nil {
		log.Printf("failed to listen: %v", err)
	}

	var devices map[int]*DeviceInfo
	errChan := make(chan error, 1) // Channel for capturing errors
	icicleRunTime.LoadBackendFromEnvOrDefault()
	device := icicleRunTime.CreateDevice("CUDA", 0)
	icicleRunTime.RunOnDevice(&device, func(args ...any) {
		var localErr error
		devices, localErr = loadDevice()
		errChan <- localErr // Send error to channel
	})
	err = <-errChan // Read error from channel
	if err != nil {
		log.Printf("failed to bind device: %v", err)
	}

	s := grpc.NewServer()
	log.Printf("Successfully, bind port: %v", *port)
	pb.RegisterProveServiceServer(s, &server{
		circuits: circuits, // Pass loaded circuits to server instance
		devices:  devices,
	})

	if err := s.Serve(lis); err != nil {
		log.Printf("failed to serve: %v", err)

	}
}
