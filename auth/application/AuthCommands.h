#pragma once
#include <string>
namespace mirage::auth
{
struct RegisterUserCommand
{
    std::string name, email, password;
};
struct LoginCommand
{
    std::string email, password;
};
struct GoogleSignInCommand
{
    std::string idToken, nonce;
};
struct RefreshSessionCommand
{
    std::string refreshToken;
};
struct LogoutCommand
{
    std::string bearer;
};
struct RecoverPasswordCommand
{
    std::string email;
};
struct ResetPasswordCommand
{
    std::string bearer, password;
};
struct ResendVerificationCommand
{
    std::string email;
};
struct VerifyEmailCommand
{
    std::string email, token, type;
};
struct GetCurrentUserQuery
{
    std::string bearer;
};
} // namespace mirage::auth
