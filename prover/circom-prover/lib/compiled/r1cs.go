package compiled

import (
	"math/big"
	"strings"
)

// R1CS decsribes a set of R1C constraint
type R1CS struct {
	ConstraintSystem
	Constraints []R1C
}

// GetNbConstraints returns the number of constraints
func (r1cs *R1CS) GetNbConstraints() int {
	return len(r1cs.Constraints)
}

// R1C used to compute the wires
type R1C struct {
	L, R, O LinearExpression
}

func (r1c *R1C) String(coeffs []big.Int) string {
	var sbb strings.Builder
	sbb.WriteString("L[")
	r1c.L.string(&sbb, coeffs)
	sbb.WriteString("] * R[")
	r1c.R.string(&sbb, coeffs)
	sbb.WriteString("] = O[")
	r1c.O.string(&sbb, coeffs)
	sbb.WriteString("]")

	return sbb.String()
}
