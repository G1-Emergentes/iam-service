#pragma once
#include "../../profile/application/ProfileServices.h"
#include "AuthCommandService.h"
namespace mirage::auth
{
// Coordinates account sessions with Profile through its application boundary.
class AccountService
{
    const AuthCommandService &commands_;
    const profile::ProfileCommandService &profileCommands_;
    const profile::ProfileQueryService &profileQueries_;
    std::function<std::string()> newProfileId_;
    Completion sessionCompletion(Completion, bool allowPendingConfirmation = false) const;
    void ensureProfile(ApiResult, Completion) const;
    void rejectSession(const std::string &bearer, Completion) const;

  public:
    AccountService(const AuthCommandService &commands,
                   const profile::ProfileCommandService &profileCommands,
                   const profile::ProfileQueryService &profileQueries,
                   std::function<std::string()> newProfileId)
        : commands_(commands), profileCommands_(profileCommands), profileQueries_(profileQueries),
          newProfileId_(std::move(newProfileId))
    {
    }
    void handle(const RegisterUserCommand &, Completion) const;
    void handle(const LoginCommand &, Completion) const;
    void handle(const GoogleSignInCommand &, Completion) const;
    void handle(const VerifyEmailCommand &, Completion) const;
};
} // namespace mirage::auth
