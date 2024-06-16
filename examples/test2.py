from qiskit_aer import AerSimulator
from qiskit import QuantumCircuit, transpile
# from qiskit.transpiler import PassManager
from qiskit_ibm_runtime.transpiler.passes.scheduling import ALAPScheduleAnalysis
from qiskit_ibm_runtime.transpiler.passes.scheduling import PadDelay
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit.transpiler.passmanager import PassManager
# from qiskit.transpiler.passes import ALAPScheduleAnalysis, TimeUnitConversion
from qiskit_ibm_runtime.transpiler.passes.scheduling import DynamicCircuitInstructionDurations
from qiskit_ibm_runtime.fake_provider import FakeJakartaV2
from qiskit.compiler import schedule
from qiskit_ibm_runtime import QiskitRuntimeService
from qiskit_ibm_runtime.options import SimulatorOptions
from qiskit_ibm_runtime.fake_provider import FakeJakartaV2


qc = QuantumCircuit.from_qasm_file("benchmarks/qc2.qasm")
backend = FakeJakartaV2()

qc = transpile(qc, backend = backend)



