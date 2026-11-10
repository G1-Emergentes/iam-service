#pragma once
#include "AuthCommands.h"
#include "IdentityProvider.h"
namespace mirage::auth
{
class AuthCommandService
{
    const IdentityProvider &provider_;

  public:
    explicit AuthCommandService(const IdentityProvider &provider) : provider_(provider) {}
    void handle(const RegisterUserCommand &, Completion) const;
    void handle(const LoginCommand &, Completion) const;
    void handle(const GoogleSignInCommand &, Completion) const;
    void handle(const RefreshSessionCommand &, Completion) const;
    void handle(const LogoutCommand &, Completion) const;
    void handle(const RecoverPasswordCommand &, Completion) const;
    void handle(const ResetPasswordCommand &, Completion) const;
    void handle(const ResendVerificationCommand &, Completion) const;
    void handle(const VerifyEmailCommand &, Completion) const;
};
class AuthQueryService
{
    const IdentityProvider &provider_;

  public:
    explicit AuthQueryService(const IdentityProvider &provider) : provider_(provider) {}
    void handle(const GetCurrentUserQuery &query, Completion done) const
    {
        provider_.execute(IdentityOperation::GetUser, {}, query.bearer, std::move(done));
    }
};
} // namespace mirage::auth
