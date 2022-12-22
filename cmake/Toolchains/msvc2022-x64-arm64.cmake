set(CMAKE_SYSTEM_NAME Windows)

#set(CMAKE_C_COMPILER "C:/Program Files/Microsoft Visual Studio/2022/Enterprise/VC/Tools/MSVC/14.34.31933/bin/Hostx64/arm64/cl.exe")
#set(CMAKE_CXX_COMPILER "C:/Program Files/Microsoft Visual Studio/2022/Enterprise/VC/Tools/MSVC/14.34.31933/bin/Hostx64/arm64/cl.exe")
#set(CMAKE_ASM_COMPILER "C:/Program Files/Microsoft Visual Studio/2022/Enterprise/VC/Tools/MSVC/14.34.31933/bin/Hostx64/arm64/cl.exe")

set(CMAKE_CROSSCOMPILING 1)
#set(CMAKE_GENERATOR "Visual Studio 17 2022")
#set(CMAKE_GENERATOR_PLATFORM ARM64 CACHE INTERNAL "")
set(CMAKE_SYSTEM_PROCESSOR ARM64)
set(CMAKE_HOST_SYSTEM_PROCESSOR x64)
set(CMAKE_ASM_MASM_COMPILER armasm64)