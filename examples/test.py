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

# QiskitRuntimeService.save_account(channel="ibm_quantum", token='6be65f0ec78a1145f69c8dfeda2633401927ed71e9f1e918705862fcec493605c0743c8fa3dc97ad4dfb45472097a4acc3e6ad34b4abf26c8a97193065b62929')
# service = QiskitRuntimeService(instance="ibm-q/open/main")
# backend = service.backend('ibm_osaka')
# Create a quantum circuit
# qc = QuantumCircuit(2)
# qc.h(0)
# qc.cx(0, 1)
# qc.measure_all()
qc = QuantumCircuit.from_qasm_file("benchmarks/qc2.qasm")
backend = FakeJakartaV2()

qc = transpile(qc, backend = backend)

durations = DynamicCircuitInstructionDurations.from_backend(backend)
# print("-----------------------------------------------")
# print(f"This is duration: \n{durations}\nDuration ends")
# print("-----------------------------------------------")
pm = generate_preset_pass_manager(optimization_level=1, backend=backend)
pm.scheduling = PassManager([ALAPScheduleAnalysis(durations)])
for instr, qargs, _ in qc.data:
    qubit_indices = [q._index for q in qargs]
    duration = durations.get(instr.name, qubit_indices)
transpiled_circuit = transpile(qc, backend)
scheduled_pulse = schedule(transpiled_circuit, backend=backend)
scheduled_circuit = pm.run(transpiled_circuit)

start_times = []
data = []
# print(f"This is scheduled_circuit: \n{scheduled_circuit}\nThis is transpiled_circuit: {transpiled_circuit}")
for i in range(len(scheduled_circuit._op_start_times)):
    # data.append(scheduled_circuit.data[i])
    instr, qargs, cargs = scheduled_circuit.data[i]
    # idxs = []
    # for qubit in qargs:
    if len(qargs) < 2:
        # idxs.append(qubit._index)
        duration = durations.get(instr.name, qargs[0]._index)
        if not duration == 0 and not instr.name=='measure':
            data.append((instr.name, instr.params, qargs[0]._index))
            start_times.append(scheduled_circuit.op_start_times[i][1])

# print(start_times, data)
# print(f"\nThis is start_time: {start_times}\n")

start_time_groups = {}
for i, start_time in enumerate(start_times):
    if start_time not in start_time_groups:
        start_time_groups[start_time] = []
    start_time_groups[start_time].append(data[i])

concurrent_gates = []
# print("\n\nstart_time groups\n", start_time_groups)
for start_time, ops in start_time_groups.items():
    # qubits_involved = set()
    # for op in ops:
    #     print(op[2])
    #     qubits_involved.update(op[2])
    # # print('involved', qubits_involved)
    # if 0 in qubits_involved and 1 in qubits_involved:
    if len(ops) > 1:
        concurrent_gates.append((start_time, ops))

# print("\n\nConcurrent gates on qubits 0 and 1:\n", concurrent_gates,"\n")
for start_time, ops in concurrent_gates:
    # print(f"Time: {start_time}")
    for op in ops:
        gate_name = op[0]
        params = op[1]
        qubits = op[2]
        # print(f"  Gate: {gate_name} on qubits {qubits} with params {params}")       
options =  SimulatorOptions()
print(options)