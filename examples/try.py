from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

# 創建一個簡單的量子電路
qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)

# 指定量子後端
backend = AerSimulator()

# 轉譯量子電路
transpiled_qc = transpile(qc, backend=backend, optimization_level=3)

# 顯示轉譯後的量子電路
print(transpiled_qc)
