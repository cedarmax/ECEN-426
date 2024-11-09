import random
import os
import subprocess
import re
import time

def write_to_file(num):
    # Convert the number to bytes in LSB first order
    byte_array = [num & 0xFF, (num >> 8) & 0xFF, (num >> 16) & 0xFF, (num >> 24) & 0xFF]

    # Create the directory if it doesn't exist
    os.makedirs("riscv_software", exist_ok=True)

    # Write to test.c in the test_vector directory
    with open("riscv_software/test.c", "w") as f:
        f.write("#include <stdio.h>\n")
        f.write("#include <stdint.h>\n\n")
        f.write("int main(void)\n")
        f.write("{\n")
        f.write("asm(\".byte " + ", ".join(f"0x{byte:02x}" for byte in byte_array) + "\");\n")
        f.write("return 0;\n")
        f.write("}\n")

def run_command(command):
    """Run a shell command and handle exceptions."""
    try:
        subprocess.run(command, check=True, shell=True)  # Run the command
    except subprocess.CalledProcessError as e:
        print(f"Command '{command}' failed with error: {e}")

def compile_riscv_software():
    
    # Initialize booleans and variables to store values
    illegal_instruction_in_cpu = False
    pc_value_cpu = None
    instruction_cpu = None
    
    illegal_instruction_in_spike = False
    epc_value_spike = None
    instruction_spike = None
    
    # Define regex patterns to match the specific lines
    cpu_pattern = r"Exception @\s+(\d+), PC: (\S+), Cause: Illegal Instruction"
    spike_pattern = r"core\s+0: exception trap_illegal_instruction, epc (\S+)"
    tval_pattern = r"tval[:\s]+(\S+)"  # Pattern to match 'tval' value in the following line
    
    # Change to the riscv_software directory and run make compile
    try:
        os.chdir("riscv_software")  # Change directory
        subprocess.run(["make", "compile"], check=True)  # Call make compile
        os.chdir("../")  # Change directory

        # Define PARENT_PATH variable
        parent_path = os.environ.get('PARENT_PATH', '/path/to/default')  # Set a default if not found
        run_command(f"{parent_path}/utils/emu_run_spike.bash {parent_path}/sim/spike t {parent_path}/riscv_software/test.mem {parent_path}/riscv_software/spike_run.log 2 {parent_path}/riscv_software/spike_trace.log")
    except FileNotFoundError:
        print("Error: Directory 'riscv_software' does not exist.")
    except subprocess.CalledProcessError as e:
        print(f"Compilation failed with error: {e}")
    
    # Search in riscv_software/spike_trace.log for Spike exception
    try:
        with open(os.path.join(parent_path, "riscv_software/spike_trace.log"), "r") as spike_log:
            for line in spike_log:
                match = re.search(spike_pattern, line)
                if match:
                    illegal_instruction_in_spike = True
                    epc_value_spike = match.group(1)
                    
                    # Look for tval in the next line
                    next_line = next(spike_log, "")
                    tval_match = re.search(tval_pattern, next_line)
                    if tval_match:
                        instruction_spike = tval_match.group(1)
                    break
    except FileNotFoundError:
        print("Error: 'riscv_software/spike_trace.log' file not found.")
    
    print("Spike Illegal Instruction:", illegal_instruction_in_spike)
    if illegal_instruction_in_spike:
        print(f"EPC Value (Spike): {epc_value_spike}, Instruction (Spike): {instruction_spike}")

    if(not (illegal_instruction_in_spike)):
        return
    if(int(instruction_spike, 16) != instruction_under_test):
        print("Not the instruction under test")
        return
    
    try:
        run_command(f"{parent_path}/utils/vcs_run_cva6.bash {parent_path}/sim/vcs_0 {os.path.join(os.environ.get('LABROOT', '/path/to/labroot'), 'chipyard_v1_7_1/cva6/dramsim2_ini')} {parent_path}/riscv_software/test.mem {parent_path}/sim/vcs_0/my_run_cva6.log 3400000 cva6_trace.log") #FIXME
    except FileNotFoundError:
        print("Error: Directory 'riscv_software' does not exist.")
    except subprocess.CalledProcessError as e:
        print(f"Compilation failed with error: {e}")
    
    # Search in sim/vcs_0/trace_hart_0.log for CPU exception
    try:
        with open(os.path.join(parent_path, "sim/vcs_0/trace_hart_0.log"), "r") as cpu_log:
            for line in cpu_log:
                match = re.search(cpu_pattern, line)
                if match:
                    illegal_instruction_in_cpu = True
                    pc_value_cpu = match.group(2)
                    
                    # Look for tval in the next line
                    next_line = next(cpu_log, "")
                    tval_match = re.search(tval_pattern, next_line)
                    if tval_match:
                        instruction_cpu = tval_match.group(1)
                    break
    except FileNotFoundError:
        print("Error: 'sim/vcs_0/trace_hart_0.log' file not found.")
    
    # Check for mismatched illegal instructions and store hidden instructions
    if illegal_instruction_in_spike and not illegal_instruction_in_cpu:
        print("Illegal instruction found in Spike but not in CPU.")
        print(f"Spike instruction: {instruction_spike}")
        hidden_instructions_found.append(instruction_spike)

    # Display results
    print("CPU Illegal Instruction:", illegal_instruction_in_cpu)
    if illegal_instruction_in_cpu:
        print(f"PC Value (CPU): {pc_value_cpu}, Instruction (CPU): {instruction_cpu}")

# Function to get the opcode from a 32-bit instruction
def get_opcode(instruction):
    return instruction & 0x7F

# Function to check the type of an immediate instruction based on opcode
def get_instruction_type(opcode):
    opcode_bin = format(opcode, '07b')
    for instr_type, opcodes in immediate_opcodes.items():
        if opcode_bin in opcodes:
            return instr_type
    return None

# Function to generate a unique identifier for non-immediate fields of an instruction
def generate_identifier(instruction, instr_type):
    opcode = get_opcode(instruction)  # 7-bit opcode
    rd = (instruction >> 7) & 0x1F    # 5-bit destination register
    funct3 = (instruction >> 12) & 0x7  # 3-bit funct3 field

    # For each type, exclude the immediate field but include relevant fields
    if instr_type == 'I-type':
        rs1 = (instruction >> 15) & 0x1F  # 5-bit source register 1
        return ('I-type', opcode, funct3, rd, rs1)
    elif instr_type == 'S-type':
        rs1 = (instruction >> 15) & 0x1F  # 5-bit source register 1
        rs2 = (instruction >> 20) & 0x1F  # 5-bit source register 2
        return ('S-type', opcode, funct3, rs1, rs2)
    elif instr_type == 'U-type':
        return ('U-type', opcode, rd)     # Only opcode and rd matter for U-type
    elif instr_type == 'J-type':
        return ('J-type', opcode, rd)     # Only opcode and rd matter for J-type
    return None

# Initialize a list to store hidden instructions found in Spike but not in CPU
hidden_instructions_found = []

# Dictionary to store unique identifiers for already considered immediate instructions
considered_instructions = set()

##To keep record of instruction under test
instruction_under_test = 0

#Number of instructions tested so far
instructions_tested_so_far = 0

#Start Time
start_time = 0

# Define the set of opcodes for immediate-type instructions (in binary)
immediate_opcodes = {
    'I-type': ['0010011', '0000011'],  # Arithmetic and load immediate
    'S-type': ['0100011'],             # Store immediate
    'U-type': ['0110111', '0010111'],  # Load upper immediate and AUIPC
    'J-type': ['1101111']              # JAL
}

# Iterate over all 32-bit numbers, applying constraints and conditions
start_time = time.time()
for i in range(0x00000000, 0xFFFFFFFF + 1):
    # Check if the number satisfies [1:0] == 3 and [4:2] != 7
    if (i & 0b11) == 0b11 and ((i >> 2) & 0b111) != 0b111:
        # Check if the number is an immediate instruction
        opcode = get_opcode(i)
        instr_type = get_instruction_type(opcode)
        if instr_type:
            identifier = generate_identifier(i, instr_type)
            # If this instruction format has already been processed, skip it
            if identifier in considered_instructions:
                continue
            else:
                # Mark the instruction as considered and also test it
                considered_instructions.add(identifier)
                print(f"\nGenerated number: {i:08x}")
                instruction_under_test = i
                write_to_file(i)
                compile_riscv_software()
                instructions_tested_so_far += 1
        else:
            # If it's not an immediate instruction, test it
            print(f"\nGenerated number: {i:08x}")
            instruction_under_test = i
            write_to_file(i)
            compile_riscv_software()
            instructions_tested_so_far += 1
        print(f"Time elapsed is {time.time() - start_time}, Number of instruction tested so far {instructions_tested_so_far}, Sample space searched so far {i}")

# Display hidden instructions if any were found
if hidden_instructions_found:  # hidden_instructions_found is the last element in results
    print("Hidden instructions found in Spike but not in CPU:")
    for instruction in hidden_instructions_found:
        print(instruction)

