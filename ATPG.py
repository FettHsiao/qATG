import numpy as np
import qiskit
import math
from Fault import *
from Gate import *
from scipy.stats import chi2, ncx2
from qiskit.quantum_info import process_fidelity
from qiskit.providers.aer.noise import NoiseModel
from qiskit import execute, Aer
from qiskit import QuantumRegister, ClassicalRegister
from qiskit.providers.aer.noise.errors import standard_errors, ReadoutError
import statsmodels.stats.power as smp
import random

random.seed(427427)
INT_MIN = 1E-100
INT_MAX = 1E15
SEARCH_TIME = 700
sample_time = 10000
threshold = 0.01
r = 0.1
# def compression(expected_vector, observed_vector, threshold=threshold):
#     expected_vector_ = []
#     observed_vector_ = []
#     for i in range(len(expected_vector)):
#         if expected_vector[i] >= threshold:
#             expected_vector_.append(expected_vector[i])
#             observed_vector_.append(observed_vector[i])

#     expected_vector_.append(1-sum(expected_vector_))
#     observed_vector_.append(1-sum(observed_vector_))
#     # print("before", expected_vector, observed_vector)
#     # print("after", expected_vector, observed_vector)
#     return np.array(expected_vector_), np.array(observed_vector_)

def compression_forfault(expected_vector, observed_vector, fault_index):
    if not fault_index:
        return np.array(expected_vector), np.array(observed_vector)
    fault_index = deepcopy(fault_index)
    fault_index.sort()
    expected_vector_ = np.zeros(2**len(fault_index))
    observed_vector_ = np.zeros(2**len(fault_index))
    index_list = []
    if (len(fault_index)==2):
        index_list.append(0)
        index_list.append(2**fault_index[0])
        index_list.append(2**fault_index[1])
        index_list.append(2**fault_index[0] + 2**fault_index[1])
        # count = np.zeros(4)
        for n in range(len(expected_vector)):
            if(n & index_list[1] and n & index_list[2]):
                expected_vector_[3] += expected_vector[n]
                observed_vector_[3] += observed_vector[n]
                # count[3] += 1
            elif(n & index_list[2]):
                expected_vector_[2] += expected_vector[n]
                observed_vector_[2] += observed_vector[n]
                # count[2] += 1
            elif(n & index_list[1]):
                expected_vector_[1] += expected_vector[n]
                observed_vector_[1] += observed_vector[n]
                # count[1] += 1
            else:
                expected_vector_[0] += expected_vector[n]
                observed_vector_[0] += observed_vector[n]
                # count[0] += 1
        # print(count)

    else:
        index_list.append(0)
        index_list.append(2**fault_index[0])

        for n in range(len(expected_vector)):
            if(n & index_list[1]):
                expected_vector_[1] += expected_vector[n]
                observed_vector_[1] += observed_vector[n]
            else:
                expected_vector_[0] += expected_vector[n]
                observed_vector_[0] += observed_vector[n]
    # if(np.sum(expected_vector_) != 1 or np.sum(observed_vector_)!=1):
    #     print("EEEEEEEEEEE")
    #     print(expected_vector_, observed_vector_)
    # print(index_list)
    # print(observed_vector_)
    return np.array(expected_vector_), np.array(observed_vector_)

def to_np(vector):
    if(type(vector)==dict or type(vector)==list):
        probability = np.zeros(len(vector))
        for i in vector:
            probability[int(i, 2)] = vector[i]
    else:
        probability = vector

    probability = probability/np.sum(probability)
    return probability

class Configuration():
    def __init__(self, qc_faulty_list, qc_faultfree, length, fault_list):
        self.qc_faulty_list = qc_faulty_list
        self.qc_faultfree = qc_faultfree
        self.length = length
        self.fault_list = fault_list
        self.repetition_list = []
        self.max_repetition = INT_MAX
        self.sim_faulty_distribution_list = []
        self.sim_faultfree_distribution = []
        self.sim_overkill = INT_MAX
        self.sim_testescape = []
        self.template = []
        self.real_faulty_distribution = []
        self.boundary = 0

        #if 1 is simulation result
        self.real_faulty_distribution_list_1 = []
        self.real_faultfree_distribution_1 = []
        self.real_overkill_1 = INT_MAX
        self.real_testescape_1 = []
        #if 2 is simulation result
        self.real_faulty_distribution_list_2 = []
        self.real_faultfree_distribution_2 = []
        self.real_overkill_2 = INT_MAX
        self.real_testescape_2 = []

    def __str__(self):
        target_fault = ""
        myself = ""
        for i in self.fault_list:
            target_fault += "\n"+str(i)
        myself += "Target fault:"+target_fault+"\n"
        myself += "Length:"+str(self.length)+"     Repetition:"+str(self.max_repetition)+"      Cost:"+str(self.length*self.max_repetition)+"\n"
        myself += "overkill:"+str(self.sim_overkill)+"\n"
        myself += "testescape:"+str(self.sim_testescape)+"\n"
        # myself += str(self.faultfree_distribution)+"\n"
        # myself += str(self.faulty_distribution_list[0])+"\n"

        # self.check_bit()
        return myself

    def cal_testescape_new(self, expectd_faulty_distribution_list, observed_faulty_distribution_list, fault_index=[], alpha=0.99):
        max_repetition = self.max_repetition
        if not fault_index:
            fault_index = []
            for f in self.fault_list:
                fault_index.append(f.index)
        
        testescape_list = []
        for i in range(len(expectd_faulty_distribution_list)):
            testescape = 0
            expected_vector, observed_vector = compression_forfault(expectd_faulty_distribution_list[i], observed_faulty_distribution_list[i], fault_index[i])
                
            expected_data = expected_vector * max_repetition
            vector_length = len(expected_vector)
            chi_value = self.boundary#chi2.ppf(alpha, vector_length-1)

            for _ in range(sample_time):
                observed_sampled_data = random.choices(range(observed_vector.shape[0]), weights=observed_vector, cum_weights=None, k=max_repetition)
                observed_data = np.zeros(observed_vector.shape[0])
                for d in observed_sampled_data:
                    observed_data[d]+=1

                delta_square = np.square(expected_data - observed_data)
                chi_statistic = np.sum(delta_square/(expected_data+INT_MIN))
                if(chi_statistic>chi_value):
                    testescape+=1
            testescape_list.append(testescape/sample_time)
        return testescape_list

    def cal_overkill_new(self, faultfree_distribution, faulty_distribution_list, fault_index=[], alpha=0.99):
        max_repetition = self.max_repetition
        if not fault_index:
            fault_index = []
            for f in self.fault_list:
                fault_index.append(f.index)

        overkill = 0
        expected_data = []
        observed_vector = []
        for i in range(len(faulty_distribution_list)):
            expected_vector_, observed_vector_ = compression_forfault(faulty_distribution_list[i], faultfree_distribution, fault_index[i])
            expected_data.append(expected_vector_ * max_repetition)
            observed_vector.append(observed_vector_)

        chi_value = self.boundary#chi2.ppf(alpha, observed_vector[0].shape[0]-1)
        for _ in range(sample_time):
            for i in range(len(faulty_distribution_list)):
                observed_sampled_data = random.choices(range(observed_vector[i].shape[0]), weights=observed_vector[i], cum_weights=None, k=max_repetition)
                observed_data = np.zeros(observed_vector[i].shape[0])
                for d in observed_sampled_data:
                    observed_data[d]+=1

                delta_square = np.square(expected_data[i] - observed_data)
                chi_statistic = np.sum(delta_square/(expected_data[i]+INT_MIN))
                if(chi_statistic<=chi_value):
                    overkill+=1
                    break
        return overkill/sample_time

    # def cal_testescape(self, expectd_faulty_distribution_list, observed_faulty_distribution_list, alpha):
    #     testescape_list = []
    #     for i in range(len(expectd_faulty_distribution_list)):
    #         testescape = 0
    #         # print(expectd_faulty_distribution_list[i], observed_faulty_distribution_list[i])
    #         expected_vector, observed_vector = compression(expectd_faulty_distribution_list[i], observed_faulty_distribution_list[i])
    #         # expected_vector, observed_vector = expectd_faulty_distribution_list[i], observed_faulty_distribution_list[i]
    #         # print(expected_vector, observed_vector)
    #         expected_data = expected_vector * self.max_repetition
    #         vector_length = len(expected_vector)
    #         chi_value = chi2.ppf(alpha, vector_length-1)

    #         for _ in range(sample_time):
    #             observed_sampled_data = random.choices(range(vector_length), weights=observed_vector, cum_weights=None, k=self.max_repetition)
    #             observed_data = np.zeros(vector_length)
    #             for d in observed_sampled_data:
    #                 observed_data[d]+=1

    #             delta_square = np.square(expected_data - observed_data)
    #             chi_statistic = np.sum(delta_square/(expected_data+INT_MIN))
    #             if(chi_statistic>chi_value):
    #                 testescape+=1
    #         testescape_list.append(testescape/sample_time)
    #     return testescape_list

    # def cal_overkill(self, faultfree_distribution, faulty_distribution_list, alpha):
    #     vector_length = len(faultfree_distribution)

    #     expected_data_list = []
    #     index_data_list = []
    #     for faultydistribution in faulty_distribution_list:
    #         temp_list = [] 
    #         temp_value = 0
    #         distribution_list = []
    #         have_value = False
    #         for i in range(len(faultydistribution)):
    #             if faultydistribution[i]<threshold:
    #                 temp_list.append(i)
    #                 temp_value += faultydistribution[i]
    #                 have_value = True
    #             else:
    #                 distribution_list.append(faultydistribution[i])

    #         if(have_value):
    #             distribution_list.append(temp_value)
    #         expected_data_list.append(np.array(distribution_list) * self.max_repetition)
    #         index_data_list.append(temp_list)

    #     overkill = 0
    #     for _ in range(sample_time):
    #         observed_sampled_data = random.choices(range(vector_length), weights=faultfree_distribution, cum_weights=None, k=self.max_repetition)
    #         observed_data = np.zeros(vector_length)
    #         for d in observed_sampled_data:
    #             observed_data[d]+=1

    #         for i in range(len(expected_data_list)):
    #             temp_data = []
    #             temp = 0
    #             have_value = False
    #             for n in range(vector_length):
    #                 if n in index_data_list[i]:
    #                     # print("add:", n)
    #                     have_value = True
    #                     temp += observed_data[n]
    #                 else:
    #                     # print("append:", n)
    #                     temp_data.append(observed_data[n])
    #             if(have_value):
    #                 # print("append temp:", temp)
    #                 temp_data.append(temp)
    #             # if(len(expected_data_list[i]) != len(temp_data)):
    #             #     print(expected_data_list[i])
    #             #     print(temp_data)
    #             #     print(self.max_repetition)
    #             #     print(observed_data)
    #             if(len(expected_data_list[i]) != len(temp_data)):
    #                 print(expected_data_list[i], temp_data, )
    #             delta_square = np.square(expected_data_list[i] - temp_data)
    #             chi_value = chi2.ppf(alpha, len(delta_square)-1)
    #             chi_statistic = np.sum(delta_square/(expected_data_list[i]+INT_MIN))
    #             if(chi_statistic<=chi_value):
    #                 overkill+=1
    #                 break
    #     return overkill/sample_time

    def simulate_real_circuit(self, qc, backend, shots, times, circuit_size=5):
        summantion = {}
        for i in range(2**circuit_size):
            summantion['{0:b}'.format(i).zfill(circuit_size)] = 0

        for t in range(times):
            job_sim = execute(qc, backend, shots=shots)
            counts = job_sim.result().get_counts()
            for i in counts:
                summantion[i] += counts[i]
            print("finish ", t, " times")

        probability = np.zeros(len(summantion))
        for i in summantion:
            probability[int(i, 2)] = summantion[i]
        probability = probability/np.sum(probability)
        return(probability)

    def simulate_faulty_real_circuit(self, backend):
        for i in range(len(self.qc_faulty_list)):
            cut_list = []
            for _ in range(75):
                cut_list.append(self.qc_faulty_list[i])
            jobs = execute(cut_list, backend, shots=self.max_repetition)

            for d in range(75):
                summantion = {}
                for s in range(2**5):
                    summantion['{0:b}'.format(s).zfill(5)] = 0
                counts = jobs.result().get_counts(d)
                for c in counts:
                    summantion[c] += counts[c]
                self.real_faulty_distribution_list_2[i].append(to_np(summantion))
            print("finish", i, "faulty circuit, # of data:", len(self.real_faulty_distribution_list_2[i]))

    def simulate_faultfree_real_circuit(self, backend):
        cut_list = []
        for _ in range(75):
            cut_list.append(self.qc_faultfree)
        jobs = execute(cut_list, backend, shots=self.max_repetition)

        for d in range(75):
            summantion = {}
            for s in range(2**5):
                summantion['{0:b}'.format(s).zfill(5)] = 0
            counts = jobs.result().get_counts(d)
            for c in counts:
                summantion[c] += counts[c]
            self.real_faultfree_distribution_2.append(to_np(summantion))
        print(" # of data:", len(self.real_faultfree_distribution_2))

class ATPG():
    def __init__(self, circuit_size, qr_name='q', cr_name='c'):
        self.circuit_size = circuit_size
        self.qr_name = qr_name
        self.cr_name = cr_name
        self.quantumregister = qiskit.QuantumRegister(self.circuit_size, self.qr_name)
        self.classicalregister = qiskit.ClassicalRegister(self.circuit_size, self.cr_name)
        self.noise_model = self.get_noise_model()
        self.backend = Aer.get_backend('qasm_simulator')
        self.step = 0.01
        self.configuration_list = []
        self.alpha = 0.99
        self.beta = 0.9999
        return

    def get_fault_list(self, coupling_map):
        #return (single_fault_list two_fault_list)
        single_fault_list = []
        #U3
        for ratio in [[1-r, 1, 1], [1, 1-r, 1], [1, 1, 1-r]]:
            U3_v_fault = []
            for qb in range(self.circuit_size):
                U3_v_fault.append(U3_variation_fault([qb], ratio=ratio))
            single_fault_list.append(U3_v_fault)


        for bias in [[r*np.pi, 0, 0], [0, r*np.pi, 0], [0, 0, r*np.pi]]:
            U3_v_fault = []
            for qb in range(self.circuit_size):
                U3_v_fault.append(U3_variation_fault([qb], bias=bias))
            single_fault_list.append(U3_v_fault)

        for threshold in [[1.5*np.pi, 2*np.pi, 2*np.pi], [2*np.pi, 1.5*np.pi, 2*np.pi], [2*np.pi, 2*np.pi, 1.5*np.pi]]:
            U3_t_fault = []
            for qb in range(self.circuit_size):
                U3_t_fault.append(U3_threshold_lopa([qb], threshold=threshold))
            single_fault_list.append(U3_t_fault)


        # U2
        for ratio in [[1-r, 1], [1, 1-r]]:
            U2_v_fault = []
            for qb in range(self.circuit_size):
                U2_v_fault.append(U2_variation_fault([qb], ratio=ratio))
            single_fault_list.append(U2_v_fault)

        for bias in [[r*np.pi, 0], [0, r*np.pi]]:
            U2_v_fault = []
            for qb in range(self.circuit_size):
                U2_v_fault.append(U2_variation_fault([qb], bias=bias))
            single_fault_list.append(U2_v_fault)

        for threshold in [[1.5*np.pi, 2*np.pi], [2*np.pi, 1.5*np.pi]]:
            U2_t_fault = []
            for qb in range(self.circuit_size):
                U2_t_fault.append(U2_threshold_lopa([qb], threshold=threshold))
            single_fault_list.append(U2_t_fault)

        #U1
        for ratio in [[1-r]]:
            U1_v_fault = []
            for qb in range(self.circuit_size):
                U1_v_fault.append(U1_variation_fault([qb], ratio=ratio))
            single_fault_list.append(U1_v_fault)

        for bias in [[r*np.pi]]:
            U1_v_fault = []
            for qb in range(self.circuit_size):
                U1_v_fault.append(U1_variation_fault([qb], bias=bias))
            single_fault_list.append(U1_v_fault)

        for threshold in [[1.5*np.pi]]:
            U1_t_fault = []
            for qb in range(self.circuit_size):
                U1_t_fault.append(U1_threshold_lopa([qb], threshold=threshold))
            single_fault_list.append(U1_t_fault)

        two_fault_list = []
        #CNOT
        #[0.012, 0.023, 0.045, 0.033, 0.019, 0.006], [0.19, -0.17, 0.13, -0.22, 0.18, -0.15] [0.1, 0.1, 0.1, 0.1, 0.1, 0.1], [0.13, -0.12, 0.18, 0.24, -0.10, -0.17]
        # [0.19, -0.17, 0.13, -0.22, 0.18, -0.15], [0.13, -0.12, 0.18, 0.24, -0.10, -0.17]
        value = 0.05*np.pi
        f = [[value, value, value, value, value, value], [value, value, -value, value, value, -value], [value, -value, value, value, -value, value] , [value, -value, -value, value, -value, -value],
            [-value, value, value, -value, value, value], [-value, value, -value, -value, value, -value], [-value, -value, value, -value, -value, value] , [-value, -value, -value, -value, -value, -value]]
        # f = [[value, value, value, value, value, value]]
        for value in f:
        # for value in [[0.19, -0.17, 0.13, -0.22, 0.18, -0.15]]:
            one_type_fault = []
            drop_fault = [] 
            while len(drop_fault) != len(coupling_map):
                CNOT_v_fault = []
                for i in range(len(coupling_map)):
                    if coupling_map[i] in drop_fault:
                        continue
                    if len(CNOT_v_fault) == 0:
                        CNOT_v_fault.append(CNOT_variation_fault(coupling_map[i], value=value))
                        drop_fault.append(coupling_map[i])
                    else:
                        push_fault = True
                        for fault in CNOT_v_fault:
                            if fault.index[0] in coupling_map[i] or fault.index[1] in coupling_map[i]:
                                push_fault = False
                                break
                        if push_fault:
                            CNOT_v_fault.append(CNOT_variation_fault(coupling_map[i], value=value))
                            drop_fault.append(coupling_map[i])
                one_type_fault.append(CNOT_v_fault)
            # for i in range(len(coupling_map)):
            #     one_type_fault.append([CNOT_variation_fault(coupling_map[i], value=value)])
            two_fault_list.append(deepcopy(one_type_fault))
        return (single_fault_list, two_fault_list)

    def get_quantum_gate(self, gate_type, index, parameter=[]):
        if type(index) != list :
            index = [index]

        if(gate_type == qiskit.extensions.standard.u3.U3Gate):
            return (gate_type(parameter[0], parameter[1], parameter[2]), [qiskit.circuit.quantumregister.Qubit(QuantumRegister(self.circuit_size, self.qr_name), index[0])], [])
        elif(gate_type == qiskit.extensions.standard.u2.U2Gate):
            return (gate_type(parameter[0], parameter[1]), [qiskit.circuit.quantumregister.Qubit(QuantumRegister(self.circuit_size, self.qr_name), index[0])], [])
        elif(gate_type == qiskit.extensions.standard.u1.U1Gate):
            return (gate_type(parameter[0]), [qiskit.circuit.quantumregister.Qubit(QuantumRegister(self.circuit_size, self.qr_name), index[0])], [])
        elif(gate_type == qiskit.extensions.standard.x.CnotGate):
            return (gate_type(),[qiskit.circuit.quantumregister.Qubit(QuantumRegister(self.circuit_size, self.qr_name), index[0]), 
                            qiskit.circuit.quantumregister.Qubit(QuantumRegister(self.circuit_size, self.qr_name), index[1])], [])
        elif(gate_type == qiskit.extensions.standard.barrier.Barrier):
            return (gate_type(1), [qiskit.circuit.quantumregister.Qubit(QuantumRegister(self.circuit_size, self.qr_name), index[0])], [])

    def get_test_configuration(self, single_fault_list, two_fault_list, initial_state=np.array([1, 0])):
        configuration_list = []

        for fault_type in single_fault_list:
            template = self.generate_test_template(fault_type[0], np.array([1, 0]), self.get_single_gradient, cost_ratio=2)
            configuration = self.build_single_configuration(template, fault_type)
            self.simulate_configuration(configuration)
            configuration_list.append(configuration)
        print("finish build single configuration")

        if two_fault_list:
            for fault_type in two_fault_list:
                template = self.generate_test_template(fault_type[0][0], np.array([1, 0, 0, 0]), self.get_CNOT_gradient, cost_ratio=2)
                for fault_list in fault_type:
                    configuration = self.build_two_configuration(template, fault_list)
                    self.simulate_configuration(configuration)
                    configuration_list.append(configuration)
                # break
        print("finish build two configuration")

        test_cost = 0
        initial_time = 0
        overkill = []
        testescape = []
        for configuration in configuration_list:
            test_cost += configuration.max_repetition*configuration.length
            initial_time += configuration.max_repetition
            overkill.append(configuration.sim_overkill)
            for i in configuration.sim_testescape:
                testescape.append(i)
        overall_overkill = 1
        for i in overkill:
            overall_overkill *= 1-i
        print("Alpha:", self.alpha)
        print("Beta:", self.beta)
        print("Total overkill:", 1-overall_overkill)
        print("Total testescape:", np.mean(testescape))
        print("Total test cost:", test_cost)
        print("Initial time:", initial_time)
        print("Number of configuration:", len(configuration_list))
        return configuration_list

    def build_two_configuration(self, template, fault_list):
        qc_faulty_list = []
        qc_faultfree = qiskit.QuantumCircuit(self.quantumregister, self.classicalregister)
        length = template[2]
        index_array = []
        for fault in fault_list:
            index_array.append(fault.index)
            # print(fault.index)
        # print(len(fault_list), len(index_array))
        for index_pair in index_array:  ##這組電路fault在哪裡
            qc_faulty = qiskit.QuantumCircuit(self.quantumregister, self.classicalregister)
            for fault_index in index_array: ##這組電路幾個pair
                gate_index = 0
                if fault_index == index_pair:
                    while gate_index < len(template[0]):
                        qc_faulty._data.append(self.get_quantum_gate(gate_type=type(template[0][gate_index][1]), index=fault_index[0], parameter=template[0][gate_index][1].params))                
                        qc_faulty._data.append(self.get_quantum_gate(gate_type=type(template[0][gate_index][0]), index=fault_index[1], parameter=template[0][gate_index][0].params))

                        qc_faulty._data.append(self.get_quantum_gate(gate_type=type(template[0][gate_index+1]), index=fault_index[0], parameter=template[0][gate_index+1].params))
                
                        qc_faulty._data.append(self.get_quantum_gate(gate_type=qiskit.extensions.standard.barrier.Barrier, index=fault_index[0], parameter=[]))
                        qc_faulty._data.append(self.get_quantum_gate(gate_type=qiskit.extensions.standard.barrier.Barrier, index=fault_index[1], parameter=[]))
                        qc_faulty._data.append(self.get_quantum_gate(gate_type=type(template[0][gate_index+2]), index=fault_index, parameter=[]))
                        qc_faulty._data.append(self.get_quantum_gate(gate_type=qiskit.extensions.standard.barrier.Barrier, index=fault_index[0], parameter=[]))
                        qc_faulty._data.append(self.get_quantum_gate(gate_type=qiskit.extensions.standard.barrier.Barrier, index=fault_index[1], parameter=[]))

                        qc_faulty._data.append(self.get_quantum_gate(gate_type=type(template[0][gate_index+3]), index=fault_index[1], parameter=template[0][gate_index+3].params))
                        gate_index += 4
                else:
                    while gate_index < len(template[1]):
                        # print(fault_index)
                        qc_faulty._data.append(self.get_quantum_gate(gate_type=type(template[1][gate_index][1]), index=fault_index[0], parameter=template[1][gate_index][1].params))                
                        qc_faulty._data.append(self.get_quantum_gate(gate_type=type(template[1][gate_index][0]), index=fault_index[1], parameter=template[1][gate_index][0].params))
                
                        qc_faulty._data.append(self.get_quantum_gate(gate_type=qiskit.extensions.standard.barrier.Barrier, index=fault_index[0], parameter=[]))
                        qc_faulty._data.append(self.get_quantum_gate(gate_type=qiskit.extensions.standard.barrier.Barrier, index=fault_index[1], parameter=[]))
                        qc_faulty._data.append(self.get_quantum_gate(gate_type=type(template[1][gate_index+1]), index=fault_index, parameter=[]))
                        qc_faulty._data.append(self.get_quantum_gate(gate_type=qiskit.extensions.standard.barrier.Barrier, index=fault_index[0], parameter=[]))
                        qc_faulty._data.append(self.get_quantum_gate(gate_type=qiskit.extensions.standard.barrier.Barrier, index=fault_index[1], parameter=[]))
                        gate_index += 2
            
            qc_faulty.measure(self.quantumregister, self.classicalregister)
            qc_faulty_list.append(qc_faulty)
            # print("faulty")
            # print(qc_faulty)
        gate_index = 0
        while gate_index < len(template[1]):
            for fault in fault_list:##這組電路幾個pair
                qc_faultfree._data.append(self.get_quantum_gate(gate_type=type(template[1][gate_index][1]), index=fault.index[0], parameter=template[1][gate_index][1].params))                
                qc_faultfree._data.append(self.get_quantum_gate(gate_type=type(template[1][gate_index][0]), index=fault.index[1], parameter=template[1][gate_index][0].params))
                
                qc_faultfree._data.append(self.get_quantum_gate(gate_type=qiskit.extensions.standard.barrier.Barrier, index=fault.index[0], parameter=[]))
                qc_faultfree._data.append(self.get_quantum_gate(gate_type=qiskit.extensions.standard.barrier.Barrier, index=fault.index[1], parameter=[]))
                qc_faultfree._data.append(self.get_quantum_gate(gate_type=type(template[1][gate_index+1]), index=fault.index, parameter=[]))
                qc_faultfree._data.append(self.get_quantum_gate(gate_type=qiskit.extensions.standard.barrier.Barrier, index=fault.index[0], parameter=[]))
                qc_faultfree._data.append(self.get_quantum_gate(gate_type=qiskit.extensions.standard.barrier.Barrier, index=fault.index[1], parameter=[]))
            gate_index += 2
        qc_faultfree.measure(self.quantumregister, self.classicalregister)
        # print(length)
        # print("faultfree")
        # print(qc_faultfree)
        new_configuration = Configuration(qc_faulty_list, qc_faultfree, length, fault_list)
        for tt in fault_list:
            print(tt.index)
        new_configuration.template = template
        # print(new_configuration)
        return new_configuration

    def build_single_configuration(self, template, fault_list):
        length = template[2]
        qc_faulty_list = []
        for num_circuit in range(self.circuit_size):
            qc_faulty = qiskit.QuantumCircuit(self.quantumregister, self.classicalregister)
            for gate in template[0]:
                qc_faulty._data.append(self.get_quantum_gate(gate_type=type(gate), index=num_circuit, parameter=gate.params))
                qc_faulty._data.append(self.get_quantum_gate(gate_type=qiskit.extensions.standard.barrier.Barrier, index=num_circuit, parameter=[]))

            for gate in template[1]:
                for n in range(self.circuit_size):
                    if n != num_circuit:
                        qc_faulty._data.append(self.get_quantum_gate(gate_type=type(gate), index=n, parameter=gate.params))
                        qc_faulty._data.append(self.get_quantum_gate(gate_type=qiskit.extensions.standard.barrier.Barrier, index=n, parameter=[]))

            qc_faulty.measure(self.quantumregister, self.classicalregister)
            qc_faulty_list.append(qc_faulty)
            # print("faulty")
            # print(qc_faulty)
        qc_faultfree = qiskit.QuantumCircuit(self.quantumregister, self.classicalregister)
        for gate in template[1]:
            for n in range(self.circuit_size):
                qc_faultfree._data.append(self.get_quantum_gate(gate_type=type(gate), index=n, parameter=gate.params))
                qc_faultfree._data.append(self.get_quantum_gate(gate_type=qiskit.extensions.standard.barrier.Barrier, index=n, parameter=[]))
        qc_faultfree.measure(self.quantumregister, self.classicalregister)
        # print("faultfree")
        # print(qc_faultfree)
        new_configuration = Configuration(qc_faulty_list, qc_faultfree, length, fault_list)
        return new_configuration

    def generate_test_template(self, fault, quantum_state, activate_function, cost_ratio=1):
        faulty_gate_list = []
        faultfree_gate_list = []
        faulty_quantum_state, faultfree_quantum_state = deepcopy(quantum_state), deepcopy(quantum_state)

        faulty_gate_list, faultfree_gate_list, faulty_quantum_state, faultfree_quantum_state, repetition = activate_function(fault, faulty_quantum_state, faultfree_quantum_state, faulty_gate_list, faultfree_gate_list)
        effectsize = self.cal_effect_size(self.to_probability(faulty_quantum_state), self.to_probability(faultfree_quantum_state))
        # print(effectsize)
        # test_cost = (len(faultfree_gate_list)) * repetition
        # print(fault)
        for time in range(20):
            # faulty_gate_list_t, faultfree_gate_list_t, faulty_quantum_state_t, faultfree_quantum_state_t, repetition_t = activate_function(fault, faulty_quantum_state, faultfree_quantum_state, faulty_gate_list, faultfree_gate_list)
            # effectsize_t = self.cal_effect_size(self.to_probability(faulty_quantum_state_t), self.to_probability(faultfree_quantum_state_t))
            faulty_gate_list, faultfree_gate_list, faulty_quantum_state, faultfree_quantum_state, repetition = activate_function(fault, faulty_quantum_state, faultfree_quantum_state, faulty_gate_list, faultfree_gate_list)
            effectsize = self.cal_effect_size(self.to_probability(faulty_quantum_state), self.to_probability(faultfree_quantum_state))
            # print(effectsize_t)
            if repetition >= INT_MAX:
                print()
                print("error")
                print(fault)
                print(time, gate_list, faulty_quantum_state, faultfree_quantum_state)
                print()

            # if  (len(faultfree_gate_list_t)) * repetition_ < test_cost * cost_ratio:
            # if  1:
            #     effectsize = effectsize_t
            #     repetition = repetition_t
            #     faulty_gate_list = faulty_gate_list_t
            #     faultfree_gate_list = faultfree_gate_list_t
            #     faulty_quantum_state = faulty_quantum_state_t
            #     faultfree_quantum_state = faultfree_quantum_state_t
                # test_cost = (len(faultfree_gate_list)) * repetition

            if effectsize>5:
                break

        # for i in gate_list:
        #     print(i)
        # if (repetition<10):
        #     repetition = 10
        print(fault, " repetition:", repetition, " len:", (len(faultfree_gate_list)), "effectsize", effectsize)
        # print(faulty_quantum_state, faultfree_quantum_state)
        print("ideal:", self.to_probability(faulty_quantum_state), self.to_probability(faultfree_quantum_state))
        return (faulty_gate_list, faultfree_gate_list, (len(faultfree_gate_list)))

    def get_CNOT_gradient(self, fault, faulty_quantum_state, faultfree_quantum_state, faulty_gate_list, faultfree_gate_list):
        #for 2 qubit gate
        faultfree = [self.get_quantum_gate(gate_type=fault.gate_type, index=fault.index, parameter=[])]
        faulty = self.get_quantum_gate(gate_type=fault.gate_type, index=fault.index, parameter=[])
        faulty = fault.get_faulty_gate(faulty)

        faultfree_matrix = faultfree[0][0].to_matrix()
        faulty_matrix = fault.gate_type().to_matrix()
        faulty_matrix = np.dot(np.kron(faulty[0][0].to_matrix(), np.eye(2)), faulty_matrix)
        faulty_matrix = np.dot(faulty_matrix, np.kron(np.eye(2), faulty[2][0].to_matrix()))

        parameter_list = [0, 0, 0, 0, 0, 0]
        for i in range(SEARCH_TIME):
            self.two_gradient(parameter_list, faulty_matrix, faultfree_matrix, faulty_quantum_state, faultfree_quantum_state)
        faultfree_gate_list.append([qiskit.extensions.standard.u3.U3Gate(parameter_list[0], parameter_list[1], parameter_list[2]), qiskit.extensions.standard.u3.U3Gate(parameter_list[3], parameter_list[4], parameter_list[5])])
        faultfree_gate_list.append(qiskit.extensions.standard.x.CnotGate())
        
        faulty_gate_list.append([qiskit.extensions.standard.u3.U3Gate(parameter_list[0], parameter_list[1], parameter_list[2]), qiskit.extensions.standard.u3.U3Gate(parameter_list[3], parameter_list[4], parameter_list[5])])
        faulty_gate_list.append(faulty[0][0])
        faulty_gate_list.append(qiskit.extensions.standard.x.CnotGate())
        faulty_gate_list.append(faulty[2][0])

        faultfree_quantum_state = self.matrix_operation([[U3(parameter_list[0:3]), U3(parameter_list[3:6])], faultfree_matrix], faultfree_quantum_state)
        faulty_quantum_state = self.matrix_operation([[U3(parameter_list[0:3]), U3(parameter_list[3:6])], faulty_matrix], faulty_quantum_state)

        faulty_quantum_state_ = self.to_probability(faulty_quantum_state)
        faultfree_quantum_state_ = self.to_probability(faultfree_quantum_state)
        # faulty_quantum_state_, faultfree_quantum_state_ = compression(faulty_quantum_state_, faultfree_quantum_state_)        
        repetition, boundary = self.compute_repetition(faulty_quantum_state_, faultfree_quantum_state_, self.alpha, self.beta)
        return (faulty_gate_list, faultfree_gate_list, faulty_quantum_state, faultfree_quantum_state, repetition)

    def two_gradient(self, parameter_list, faulty_matrix, faultfree_matrix, faulty_quantum_state, faultfree_quantum_state):
        score = self.vector_distance(
                self.matrix_operation([[U3(parameter_list[0:3]), U3(parameter_list[3:6])], faultfree_matrix], faultfree_quantum_state), 
                self.matrix_operation([[U3(parameter_list[0:3]), U3(parameter_list[3:6])], faulty_matrix], faulty_quantum_state))
        new_parameter_list = [0]*len(parameter_list)

        for i in range(len(parameter_list)):
            parameter_list[i] += self.step
            up_score = self.vector_distance(
                self.matrix_operation([[U3(parameter_list[0:3]), U3(parameter_list[3:6])], faultfree_matrix], faultfree_quantum_state), 
                self.matrix_operation([[U3(parameter_list[0:3]), U3(parameter_list[3:6])], faulty_matrix], faulty_quantum_state))
            parameter_list[i] -= 2*self.step

            # parameter_list[i] -= self.step
            down_score = self.vector_distance(
                self.matrix_operation([[U3(parameter_list[0:3]), U3(parameter_list[3:6])], faultfree_matrix], faultfree_quantum_state), 
                self.matrix_operation([[U3(parameter_list[0:3]), U3(parameter_list[3:6])], faulty_matrix], faulty_quantum_state))
            parameter_list[i] += self.step

            if score == up_score == down_score:
                new_parameter_list[i] += self.step
            elif(up_score > score and up_score >= down_score):
                new_parameter_list[i] += self.step
            elif(down_score > score and down_score >= up_score):
                new_parameter_list[i] -= self.step
        
        for i in range(len(parameter_list)):
            parameter_list[i] += new_parameter_list[i]

        return 
    
    def get_single_gradient(self, fault, faulty_quantum_state, faultfree_quantum_state, faulty_gate_list, faultfree_gate_list):
        #for 1 qubit gate
        faultfree = [self.get_activation_gate(fault)]
        faulty = self.get_activation_gate(fault)
        
        faulty = fault.get_faulty_gate(faulty)
        # print("Start:",faulty[0][0].params)
        faultfree_matrix = faultfree[0][0].to_matrix()
        faulty_matrix = faulty[0][0].to_matrix()
        parameter_list = [0, 0, 0]

        # print(faultfree[0])
        for i in range(SEARCH_TIME):
            self.single_gradient(parameter_list, faulty_matrix, faultfree_matrix, faulty_quantum_state, faultfree_quantum_state, fault)
        
        # score = self.vector_distance(faultfree_quantum_state, faulty_quantum_state)
        faulty_parameter = self.check_fault(fault, parameter_list)
        faulty_gate_list.append(qiskit.extensions.standard.u3.U3Gate(faulty_parameter[0], faulty_parameter[1], faulty_parameter[2]))
        faulty_gate_list.append(faulty[0][0])
        
        faultfree_gate_list.append(qiskit.extensions.standard.u3.U3Gate(parameter_list[0], parameter_list[1], parameter_list[2]))
        faultfree_gate_list.append(faultfree[0][0])
        # print(faulty_matrix)
        faultfree_quantum_state = self.matrix_operation([U3(parameter_list), faultfree_matrix], faultfree_quantum_state, max_size=2)
        faulty_quantum_state = self.matrix_operation([U3(self.check_fault(fault, parameter_list)), faulty_matrix], faulty_quantum_state, max_size=2)
        # print(faultfree_quantum_state, faulty_quantum_state)
        faulty_quantum_state_ = self.to_probability(faulty_quantum_state)
        faultfree_quantum_state_ = self.to_probability(faultfree_quantum_state)
        # faulty_quantum_state_, faultfree_quantum_state_ = compression(faulty_quantum_state_, faultfree_quantum_state_)
        repetition, boundary = self.compute_repetition(faulty_quantum_state_, faultfree_quantum_state_, self.alpha, self.beta)
        # print(parameter_list, repetition)
        # print("repetition:", parameter_list, repetition)
        # print(np.array(faultfree_quantum_state*np.conj(faultfree_quantum_state)), np.array(faulty_quantum_state*np.conj(faulty_quantum_state)))
        # print(faultfree_quantum_state, faulty_quantum_state)
        return (faulty_gate_list, faultfree_gate_list, faulty_quantum_state, faultfree_quantum_state, repetition)

    def single_gradient(self, parameter_list, faulty_matrix, faultfree_matrix, faulty_quantum_state, faultfree_quantum_state, fault):

        score = self.vector_distance(
                self.matrix_operation([U3(parameter_list), faultfree_matrix], faultfree_quantum_state, max_size=2), 
                self.matrix_operation([U3(self.check_fault(fault, parameter_list)), faulty_matrix], faulty_quantum_state, max_size=2))
        new_parameter_list = [0]*len(parameter_list)
        # temp_value = 0
        for i in range(len(parameter_list)):
            parameter_list[i] += self.step
            up_score = self.vector_distance(
                self.matrix_operation([U3(parameter_list), faultfree_matrix], faultfree_quantum_state, max_size=2), 
                self.matrix_operation([U3(self.check_fault(fault, parameter_list)), faulty_matrix], faulty_quantum_state, max_size=2))

            parameter_list[i] -= 2*self.step

            down_score = self.vector_distance(
                self.matrix_operation([U3(parameter_list), faultfree_matrix], faultfree_quantum_state, max_size=2), 
                self.matrix_operation([U3(self.check_fault(fault, parameter_list)), faulty_matrix], faulty_quantum_state, max_size=2))
            parameter_list[i] += self.step


            if score == up_score == down_score:
                new_parameter_list[i] += self.step
            elif(up_score > score and up_score >= down_score):
                new_parameter_list[i] += self.step
            elif(down_score > score and down_score >= up_score):
                new_parameter_list[i] -= self.step
        for i in range(len(parameter_list)):
            parameter_list[i] += new_parameter_list[i]
        return 

    def cal_effect_size(self, expected_vector, observed_vector):
        delta_square = np.square(expected_vector - observed_vector)
        effectsize = np.sum(delta_square/(expected_vector+INT_MIN))
        effectsize = np.sqrt(effectsize)
        if(effectsize<0.1):
            # print(effectsize)
            effectsize = 0.1
        return effectsize

    def compute_repetition(self, faulty_data, faultfree_data, alpha, beta):
        if faultfree_data.shape != faulty_data.shape:
            print('input shape not consistency')
            return

        degree_freedom = faultfree_data.shape[0]-1
        effect_size = self.cal_effect_size(faulty_data, faultfree_data)
        if(effect_size>0.8):
            lower_bound_effect_size = 0.8
        else:
            lower_bound_effect_size = effect_size

        repetition = chi2.ppf(self.alpha, degree_freedom)/(lower_bound_effect_size**2)
        non_centrality = repetition*(effect_size**2)
        chi2_value = chi2.ppf(self.alpha, degree_freedom)
        non_chi2_value = ncx2.ppf(1-self.beta, degree_freedom, non_centrality)
        # print(non_chi2_value, chi2_value, repetition, effect_size, non_centrality)
        # if(chi2_value > non_chi2_value):
        # print("original", repetition)
        while(non_chi2_value<chi2_value):
            # print(non_chi2_value, chi2_value, repetition)
            repetition += 1
            non_centrality = repetition*(effect_size**2)
            chi2_value = chi2.ppf(self.alpha, degree_freedom)
            non_chi2_value = ncx2.ppf(1-self.beta, degree_freedom, non_centrality)
        # print("after", repetition, non_chi2_value, chi2_value)
        
        # repetition += 5
        # print(repetition, type(repetition))
        boundary = (non_chi2_value*0.3+chi2_value*0.7)
        # print(chi2_value, non_chi2_value, boundary, non_centrality, effect_size)
        if(repetition >= INT_MAX or repetition <= 0):
            # print("repetition error")
            # print(faultfree)
            # print(faulty)
            # print()
            return INT_MAX
        else:
            return math.ceil(repetition), boundary

    def matrix_operation(self, matrix_list, quantum_state=[], max_size=4):
        matrix = np.eye(max_size)
        for i in range(len(matrix_list)):
            if type(matrix_list[i]) == list:
                for j in range(len(matrix_list[i])-1):
                    matrix_list[i][j] = np.kron(matrix_list[i][j] , matrix_list[i][j+1])
                matrix_list[i] = matrix_list[i][-2]
            matrix = np.dot(matrix_list[i], matrix)
        if type(quantum_state) != list:
            return np.dot(matrix, quantum_state)
        else:
            return matrix

    def check_fault(self, fault, parameter_list):
        if(type(fault)==U3_variation_fault):
            return [parameter_list[0]*fault.ratio[0]+fault.bias[0],
                    parameter_list[1]*fault.ratio[1]+fault.bias[1],
                    parameter_list[2]*fault.ratio[2]+fault.bias[2]]
        elif(type(fault)==U3_threshold_lopa):
            return [fault.threshold[0] if parameter_list[0] > fault.threshold[0] else parameter_list[0],
                    fault.threshold[1] if parameter_list[1] > fault.threshold[1] else parameter_list[1],
                    fault.threshold[2] if parameter_list[2] > fault.threshold[2] else parameter_list[2]]
        else:
            return parameter_list

    def get_activation_gate(self, fault):
        if(type(fault)==U3_variation_fault or type(fault)==U2_variation_fault or type(fault)==U1_variation_fault):
            ratio = []
            bias = []
            for r in fault.ratio:
                if r<1:
                    ratio.append(2*np.pi)
                else:
                    ratio.append(0)
                bias.append(0)
            return self.get_quantum_gate(gate_type=fault.gate_type, index=fault.index, parameter=ratio)
        elif(type(fault)==U3_threshold_lopa or type(fault)==U2_threshold_lopa or type(fault)==U1_threshold_lopa):
            threshold = []
            for t in fault.threshold:
                if t<(2*np.pi):
                    threshold.append(2*np.pi-INT_MIN)
                else:
                    threshold.append(0)
            return self.get_quantum_gate(gate_type=fault.gate_type, index=fault.index, parameter=threshold)
        elif(type(fault)==qiskit.extensions.standard.x.CnotGate):
            return self.get_quantum_gate(gate_type=fault.gate_type, index=fault.index, parameter= [])

    def simulate_configuration(self, configuration, shots=200000):
        configuration.repetition_list = []
        configuration.sim_faultfree_distribution = []
        configuration.sim_faulty_distribution_list = []
        configuration.max_repetition = 0
        configuration.boundary = 0 
        
        job_sim = execute(configuration.qc_faultfree, self.backend, noise_model=self.noise_model, shots=shots)
        # job_sim = execute(configuration.qc_faultfree, self.backend, shots=shots)
        
        summantion_free = {}
        for i in range(2**self.circuit_size):
            summantion_free['{0:b}'.format(i).zfill(self.circuit_size)] = 0
        counts = job_sim.result().get_counts()
        for i in counts:
            summantion_free[i] += counts[i]
        configuration.sim_faultfree_distribution = self.to_np(summantion_free)

        for number, qc_faulty in enumerate(configuration.qc_faulty_list):
            job_sim = execute(qc_faulty, self.backend, noise_model=self.noise_model, shots=shots)
            # job_sim = execute(qc_faulty, self.backend, shots=shots)

            summantion_faulty = {}
            for i in range(2**self.circuit_size):
                summantion_faulty['{0:b}'.format(i).zfill(self.circuit_size)] = 0
            counts = job_sim.result().get_counts()
            for i in counts:
                summantion_faulty[i] += counts[i]
            configuration.sim_faulty_distribution_list.append(self.to_np(summantion_faulty)) 

            # print(configuration.sim_faulty_distribution_list[-1], configuration.sim_faultfree_distribution)
            faulty_distribution, faultfree_distribution = compression_forfault(configuration.sim_faulty_distribution_list[-1], configuration.sim_faultfree_distribution, deepcopy(configuration.fault_list[number].index))
            # faulty_distribution, faultfree_distribution = compression(configuration.sim_faulty_distribution_list[-1], configuration.sim_faultfree_distribution)
            # print(faulty_distribution, faultfree_distribution)
            repetition, boundary = self.compute_repetition(faulty_distribution, faultfree_distribution, self.alpha, self.beta)
            # effect_size = self.cal_effect_size(faulty_distribution, faultfree_distribution)
            # before = repetition
            # repetition = self.check_repetition(repetition, len(faulty_distribution)-1, effect_size, self.alpha, 1-self.beta)
            # if (repetition - before) >0:
            #     print("to reduce overkill, Add :", repetition-before, " repetitions")
            configuration.repetition_list.append((repetition, boundary))

        fault_index = []
        for f in configuration.fault_list:
            fault_index.append(f.index)

        temp_list = [0, 0]
        for c in configuration.repetition_list:
            if c[0] > temp_list[0]:
                temp_list[0] = c[0]
                temp_list[1] = c[1]

        configuration.max_repetition = temp_list[0]
        configuration.boundary = temp_list[1]
        # configuration.sim_overkill = configuration.cal_overkill(configuration.sim_faultfree_distribution, configuration.sim_faulty_distribution_list, alpha=self.alpha)
        # configuration.sim_testescape = configuration.cal_testescape(configuration.sim_faulty_distribution_list, configuration.sim_faulty_distribution_list, alpha=self.alpha)
        
        configuration.sim_overkill = configuration.cal_overkill_new(configuration.sim_faultfree_distribution, configuration.sim_faulty_distribution_list, fault_index, alpha=self.alpha)
        configuration.sim_testescape = configuration.cal_testescape_new(configuration.sim_faulty_distribution_list, configuration.sim_faulty_distribution_list, fault_index, alpha=self.alpha)
        
        
        # if(configuration.max_repetition) < 10:
        #     configuration.max_repetition = 10
        # for qc_faulty in configuration.qc_faulty_list:
        #     job_sim = execute(qc_faulty, backend, noise_model=noise_model, shots=configuration.max_repetition)
        #     summantion_faulty = {}
        #     for i in range(2**self.circuit_size):
        #         summantion_faulty['{0:b}'.format(i).zfill(self.circuit_size)] = 0
        #     counts = job_sim.result().get_counts()
        #     for i in counts:
        #         summantion_faulty[i] += counts[i]
        #     configuration.faulty_test_distribution.append(self.to_np(summantion_faulty)) 
        # print(len(self.configuration_list))
        print(configuration)

        # print("faultfree_distribution:", configuration.faultfree_distribution)
        # print("faulty_distribution:", configuration.faulty_distribution)
        return

    def simulate_circuit(self, qc, backend, shots, noise_model = False):
        if noise_model:
            noise_model = self.noise_model
            job_sim = execute(qc, backend, noise_model=noise_model, shots=shots)
        else:
            job_sim = execute(qc, backend, shots=shots)

        summantion = {}
        for i in range(2**self.circuit_size):
            summantion['{0:b}'.format(i).zfill(self.circuit_size)] = 0
        counts = job_sim.result().get_counts()
        for i in counts:
            summantion[i] += counts[i]
        
        return( self.to_np(summantion) )

    def to_np(self, vector):
        if(type(vector)==dict or type(vector)==list):
            probability = np.zeros(len(vector))
            for i in vector:
                probability[int(i, 2)] = vector[i]
        else:
            probability = vector

        probability = probability/np.sum(probability)
        return probability

    def to_probability(self, probability):
        # print(np.array(probability*np.conj(probability), dtype=float))
        return np.array(probability*np.conj(probability), dtype=float)

    def get_noise_model(self):
        # Error probabilities
        prob_1 = 0.001  # 1-qubit gate
        prob_2 = 0.01   # 2-qubit gate

        # Depolarizing quantum errors
        error_1 = standard_errors.depolarizing_error(prob_1, 1)
        error_2 = standard_errors.depolarizing_error(prob_2, 2)
        error_3 = ReadoutError([[0.985,0.015],[0.015,0.985]])

        # Add errors to noise model
        noise_model = NoiseModel()
        noise_model.add_all_qubit_quantum_error(error_1, ['u1', 'u2', 'u3'])
        noise_model.add_all_qubit_quantum_error(error_2, ['cx'])
        noise_model.add_all_qubit_readout_error(error_3)

        return noise_model
        
    def vector_distance(self, vector1, vector2):
        return np.sum(np.square(np.abs(np.subtract(self.to_probability(vector1), self.to_probability(vector2)))))