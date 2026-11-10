cmake_minimum_required (VERSION 3.10)

# 1. Decirle a CMake dónde está vcpkg en tu máquina (debe ir antes de project)
set(CMAKE_TOOLCHAIN_FILE "C:/dev/vcpkg/scripts/buildsystems/vcpkg.cmake" CACHE STRING "")

project ("iam-service")

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 2. Buscar Drogon
find_package(Drogon CONFIG REQUIRED)

# 3. Incluir archivos del proyecto
add_executable(iam-service 
    "iam-service.cpp"
    "iam-service.h"
    "AuthController.h"
    "AuthController.cpp"
    "shared/interfaces/HttpSupport.cpp"
    "shared/infrastructure/SupabaseClient.cpp"
    "auth/application/AuthCommandService.cpp"
    "auth/application/AccountService.cpp"
    "auth/infrastructure/SupabaseIdentityProvider.cpp"
    "profile/domain/model/UserProfileAggregate.cpp"
    "profile/application/ProfileServices.cpp"
    "profile/application/PreferencesService.cpp"
    "profile/infrastructure/ProfileJsonMapper.cpp"
    "profile/infrastructure/SupabaseProfileRepository.cpp"
    "profile/interfaces/ProfileController.cpp"
    "shared/interfaces/ApiDocumentation.cpp"
)

# 4. Enlazar Drogon
target_link_libraries(iam-service PRIVATE Drogon::Drogon)

# Ninja presets place the executable here; reconfigure when documentation changes.
foreach(asset index.html openapi.json swagger-ui.css swagger-ui-bundle.js swagger-initializer.js LICENSE VENDOR.md recovery.html verify.html email-flow.js email-flow.css)
    configure_file("docs/${asset}" "${CMAKE_CURRENT_BINARY_DIR}/docs/${asset}" COPYONLY)
endforeach()

include(CTest)
if(BUILD_TESTING)
    add_executable(profile-domain-tests tests/profile_domain_tests.cpp
        profile/domain/model/UserProfileAggregate.cpp profile/application/ProfileServices.cpp
        profile/application/PreferencesService.cpp)
    target_compile_features(profile-domain-tests PRIVATE cxx_std_17)
    add_test(NAME profile-domain COMMAND profile-domain-tests)

    add_executable(account-service-tests tests/account_service_tests.cpp
        auth/application/AuthCommandService.cpp auth/application/AccountService.cpp
        profile/domain/model/UserProfileAggregate.cpp profile/application/ProfileServices.cpp)
    target_compile_features(account-service-tests PRIVATE cxx_std_17)
    target_link_libraries(account-service-tests PRIVATE JsonCpp::JsonCpp)
    add_test(NAME account-service COMMAND account-service-tests)

    add_executable(auth-session-tests tests/auth_session_tests.cpp
        auth/application/AuthCommandService.cpp)
    target_compile_features(auth-session-tests PRIVATE cxx_std_17)
    target_link_libraries(auth-session-tests PRIVATE JsonCpp::JsonCpp)
    add_test(NAME auth-sessions COMMAND auth-session-tests)
endif()
