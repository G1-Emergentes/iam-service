#pragma once
#include "../../shared/application/ApiResult.h"
namespace mirage::auth
{
enum class IdentityOperation
{
    Register,
    Login,
    Google,
    Refresh,
    Logout,
    Recover,
    ResetPassword,
    ResendVerification,
    VerifyEmail,
    RevokeAllSessions,
    GetUser
};
class IdentityProvider
{
  public:
    virtual ~IdentityProvider() = default;
    virtual void execute(IdentityOperation, Json::Value payload, std::string bearer,
                         Completion) const = 0;
};
} // namespace mirage::auth
