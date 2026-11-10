#include "SupabaseIdentityProvider.h"
#include "../../shared/infrastructure/SupabaseClient.h"
namespace mirage::auth
{
void SupabaseIdentityProvider::execute(IdentityOperation operation, Json::Value payload,
                                       std::string bearer, Completion done) const
{
    const char *path = "";
    auto method = drogon::Post;
    switch (operation)
    {
    case IdentityOperation::Register:
        path = "/signup";
        break;
    case IdentityOperation::Login:
        path = "/token?grant_type=password";
        break;
    case IdentityOperation::Google:
        path = "/token?grant_type=id_token";
        break;
    case IdentityOperation::Refresh:
        path = "/token?grant_type=refresh_token";
        break;
    case IdentityOperation::Logout:
        path = "/logout?scope=local";
        break;
    case IdentityOperation::Recover:
        path = "/recover";
        break;
    case IdentityOperation::ResetPassword:
        path = "/user";
        method = drogon::Put;
        break;
    case IdentityOperation::ResendVerification:
        path = "/resend";
        break;
    case IdentityOperation::VerifyEmail:
        path = "/verify";
        break;
    case IdentityOperation::RevokeAllSessions:
        path = "/logout?scope=global";
        break;
    case IdentityOperation::GetUser:
        path = "/user";
        method = drogon::Get;
        break;
    }
    SupabaseClient::request(
        method, std::string("/auth/v1") + path, payload, bearer,
        [done = std::move(done), operation, bearer](ApiResult result) {
            if (result.status >= 500)
            {
                done(failure(result.status == 503 ? 503 : 502, result.status == 503
                                                                   ? "auth_not_configured"
                                                                   : "auth_provider_unavailable"));
                return;
            }
            if (result.status >= 400)
            {
                const int status = result.status == 429
                                       ? 429
                                       : (result.status == 401 || result.status == 403 ? 401 : 400);
                done(
                    failure(status, status == 429 ? "too_many_attempts" : "auth_request_rejected"));
                return;
            }
            if (operation == IdentityOperation::GetUser)
            {
                SupabaseClient::request(drogon::Post, "/rest/v1/rpc/mirage_session_active",
                                        Json::Value(Json::objectValue), bearer,
                                        [done = std::move(done),
                                         identity = std::move(result)](ApiResult active) mutable {
                                            if (active.status >= 400 || !active.body.isBool())
                                            {
                                                done(
                                                    failure(503, "session_validation_unavailable"));
                                                return;
                                            }
                                            if (!active.body.asBool())
                                            {
                                                done(failure(401, "session_revoked"));
                                                return;
                                            }
                                            identity.status = 200;
                                            done(std::move(identity));
                                        });
                return;
            }
            if (operation == IdentityOperation::Recover ||
                operation == IdentityOperation::ResendVerification)
            {
                result.body = Json::Value(Json::objectValue);
                result.body["message"] =
                    operation == IdentityOperation::Recover
                        ? "If the account exists, a recovery email will be sent."
                        : "If verification is pending, a confirmation email will be sent.";
            }
            result.status = 200;
            done(std::move(result));
        });
}
} // namespace mirage::auth
