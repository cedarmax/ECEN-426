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

    #if(not (illegal_instruction_in_spike)):
    #   return
    if(illegal_instruction_in_spike and (int(instruction_spike, 16) != instruction_under_test)):
        print("Not the instruction under test")
        return
    
    try:
        run_command(f"{parent_path}/utils/vcs_run_cva6.bash {parent_path}/sim/vcs_0 {os.path.join(os.environ.get('LABROOT', '/path/to/labroot'), 'chipyard_v1_7_1/cva6/dramsim2_ini')} {parent_path}/riscv_software/test.mem {parent_path}/sim/vcs_0/my_run_cva6.log 3400000 cva6_trace.log")
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
    
# Set to keep track of generated numbers
existing_numbers = set()

##To keep record of instruction under test
instruction_under_test = 0

#Number of instructions tested so far
instructions_tested_so_far = 0

#Start Time
start_time = 0

# Initialize a list to store hidden instructions found in Spike but not in CPU
hidden_instructions_found = []

#for i in range(0x00000000, 0xFFFFFFFF + 1):
start_time = time.time()
for i in range(0x00000000, 0xFFFFFFFF + 1):
    if (i & 0b11) == 0b11 and ((i >> 2) & 0b111) != 0b111:
        # Generate a unique number and write it to the file
        #generated_num = generate_number(existing_numbers)
        instruction_under_test = i
        write_to_file(i)
        # Print the generated number in hex format
        print(f"\nGenerated number: {i:08x}")
        # Compile the riscv_software and run additional commands
        compile_riscv_software()
        instructions_tested_so_far += 1
        print(f"Time elapsed is {time.time() - start_time}, Number of instruction tested so far {instructions_tested_so_far}, Sample space searched so far {i}")

# Display hidden instructions if any were found
if hidden_instructions_found:  # hidden_instructions_found is the last element in results
    print("Hidden instructions found in Spike but not in CPU:")
    for instruction in hidden_instructions_found:
        print(instruction)

