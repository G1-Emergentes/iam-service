#include "AuthCommandService.h"
namespace mirage::auth
{
void AuthCommandService::handle(const RegisterUserCommand &c, Completion done) const
{
    Json::Value p;
    p["email"] = c.email;
    p["password"] = c.password;
    p["data"]["display_name"] = c.name;
    provider_.execute(IdentityOperation::Register, p, "", std::move(done));
}
void AuthCommandService::handle(const LoginCommand &c, Completion done) const
{
    Json::Value p;
    p["email"] = c.email;
    p["password"] = c.password;
    provider_.execute(IdentityOperation::Login, p, "", std::move(done));
}
void AuthCommandService::handle(const GoogleSignInCommand &c, Completion done) const
{
    Json::Value p;
    p["provider"] = "google";
    p["id_token"] = c.idToken;
    if (!c.nonce.empty())
        p["nonce"] = c.nonce;
    provider_.execute(IdentityOperation::Google, p, "", std::move(done));
}
void AuthCommandService::handle(const RefreshSessionCommand &c, Completion done) const
{
    Json::Value p;
    p["refresh_token"] = c.refreshToken;
    provider_.execute(IdentityOperation::Refresh, p, "", std::move(done));
}
void AuthCommandService::handle(const LogoutCommand &c, Completion done) const
{
    provider_.execute(IdentityOperation::GetUser, {}, c.bearer,
                      [this, c, done = std::move(done)](ApiResult identity) {
                          if (identity.status != 200)
                          {
                              done(std::move(identity));
                              return;
                          }
                          provider_.execute(IdentityOperation::Logout, {}, c.bearer,
                                            std::move(done));
                      });
}
void AuthCommandService::handle(const RecoverPasswordCommand &c, Completion done) const
{
    Json::Value p;
    p["email"] = c.email;
    provider_.execute(IdentityOperation::Recover, p, "", std::move(done));
}
void AuthCommandService::handle(const ResetPasswordCommand &c, Completion done) const
{
    provider_.execute(
        IdentityOperation::GetUser, {}, c.bearer,
        [this, c, done = std::move(done)](ApiResult identity) {
            if (identity.status != 200)
            {
                done(std::move(identity));
                return;
            }
            Json::Value payload;
            payload["password"] = c.password;
            provider_.execute(
                IdentityOperation::ResetPassword, payload, c.bearer,
                [this, c, done = std::move(done)](ApiResult changed) {
                    if (changed.status != 200)
                    {
                        done(std::move(changed));
                        return;
                    }
                    provider_.execute(
                        IdentityOperation::RevokeAllSessions, {}, c.bearer,
                        [done = std::move(done)](ApiResult revoked) {
                            if (revoked.status != 200)
                            {
                                done(failure(503, "password_changed_session_revocation_failed"));
                                return;
                            }
                            Json::Value body;
                            body["message"] = "Password updated. Sign in again.";
                            body["reauthentication_required"] = true;
                            done({200, std::move(body)});
                        });
                });
        });
}
void AuthCommandService::handle(const ResendVerificationCommand &c, Completion done) const
{
    Json::Value payload;
    payload["email"] = c.email;
    payload["type"] = "signup";
    provider_.execute(IdentityOperation::ResendVerification, payload, "", std::move(done));
}
void AuthCommandService::handle(const VerifyEmailCommand &c, Completion done) const
{
    Json::Value payload;
    payload["email"] = c.email;
    payload["token"] = c.token;
    payload["type"] = c.type;
    provider_.execute(IdentityOperation::VerifyEmail, payload, "", std::move(done));
}
} // namespace mirage::auth
