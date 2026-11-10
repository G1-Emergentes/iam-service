#include "AuthController.h"
#include "auth/application/AccountService.h"
#include "auth/application/AuthCommandService.h"
#include "auth/infrastructure/SupabaseIdentityProvider.h"
#include "profile/infrastructure/SupabaseProfileRepository.h"
#include "shared/interfaces/HttpSupport.h"
using namespace mirage;
using namespace mirage::http;
using namespace mirage::auth;
namespace
{
const SupabaseIdentityProvider provider;
const AuthCommandService commands(provider);
const AuthQueryService queries(provider);
const profile::SupabaseProfileRepository profileRepository;
const profile::ProfileCommandService profileCommands(profileRepository);
const profile::ProfileQueryService profileQueries(profileRepository);
const AccountService accounts(commands, profileCommands, profileQueries,
                              [] { return drogon::utils::getUuid(); });
Completion respond(Callback callback)
{
    return [callback = std::move(callback)](ApiResult result) {
        reply(callback, static_cast<HttpStatusCode>(result.status), result.body);
    };
}
} // namespace
void AuthController::registerUser(const HttpRequestPtr &req, Callback &&callback)
{
    Json::Value body;
    if (!json(req, body, callback))
        return;
    if (!email(body) || !field(body, "password", 8, 128) || !field(body, "name", 1, 100))
    {
        error(callback, k400BadRequest, "invalid_registration");
        return;
    }
    accounts.handle(RegisterUserCommand{body["name"].asString(), body["email"].asString(),
                                        body["password"].asString()},
                    respond(std::move(callback)));
}

void AuthController::login(const HttpRequestPtr &req, Callback &&callback)
{
    Json::Value body;
    if (!json(req, body, callback))
        return;
    if (!email(body) || !field(body, "password", 1, 128))
    {
        error(callback, k400BadRequest, "invalid_credentials_format");
        return;
    }
    if (!loginAllowed(req, callback))
        return;
    accounts.handle(LoginCommand{body["email"].asString(), body["password"].asString()},
                    respond(std::move(callback)));
}

void AuthController::google(const HttpRequestPtr &req, Callback &&callback)
{
    Json::Value body;
    if (!json(req, body, callback))
        return;
    if (!field(body, "id_token", 1, 8192) ||
        (body.isMember("nonce") && !field(body, "nonce", 1, 256)))
    {
        error(callback, k400BadRequest, "invalid_google_token");
        return;
    }
    if (!loginAllowed(req, callback))
        return;
    accounts.handle(
        GoogleSignInCommand{body["id_token"].asString(), body.get("nonce", "").asString()},
        respond(std::move(callback)));
}

void AuthController::refresh(const HttpRequestPtr &req, Callback &&callback)
{
    Json::Value body;
    if (!json(req, body, callback))
        return;
    if (!field(body, "refresh_token", 1, 8192))
    {
        error(callback, k400BadRequest, "refresh_token_required");
        return;
    }
    commands.handle(RefreshSessionCommand{body["refresh_token"].asString()},
                    respond(std::move(callback)));
}

void AuthController::me(const HttpRequestPtr &req, Callback &&callback)
{
    std::string token;
    if (bearer(req, token, callback))
        queries.handle(GetCurrentUserQuery{token}, respond(std::move(callback)));
}

void AuthController::logout(const HttpRequestPtr &req, Callback &&callback)
{
    std::string token;
    if (bearer(req, token, callback))
        commands.handle(LogoutCommand{token}, respond(std::move(callback)));
}

void AuthController::forgotPassword(const HttpRequestPtr &req, Callback &&callback)
{
    Json::Value body;
    if (!json(req, body, callback))
        return;
    if (!email(body))
    {
        error(callback, k400BadRequest, "invalid_email");
        return;
    }
    commands.handle(RecoverPasswordCommand{body["email"].asString()}, respond(std::move(callback)));
}

void AuthController::resetPassword(const HttpRequestPtr &req, Callback &&callback)
{
    std::string token;
    if (!bearer(req, token, callback))
        return;
    Json::Value body;
    if (!json(req, body, callback))
        return;
    if (!field(body, "password", 8, 128))
    {
        error(callback, k400BadRequest, "invalid_password");
        return;
    }
    commands.handle(ResetPasswordCommand{token, body["password"].asString()},
                    respond(std::move(callback)));
}

void AuthController::resendVerification(const HttpRequestPtr &req, Callback &&callback)
{
    Json::Value body;
    if (!json(req, body, callback))
        return;
    if (!email(body))
    {
        error(callback, k400BadRequest, "invalid_email");
        return;
    }
    commands.handle(ResendVerificationCommand{body["email"].asString()},
                    respond(std::move(callback)));
}
void AuthController::verifyEmail(const HttpRequestPtr &req, Callback &&callback)
{
    Json::Value body;
    if (!json(req, body, callback))
        return;
    const auto type = body.get("type", "");
    if (!email(body) || !field(body, "token", 6, 10) || !type.isString() ||
        (type.asString() != "signup" && type.asString() != "recovery"))
    {
        error(callback, k400BadRequest, "invalid_verification");
        return;
    }
    const auto code = body["token"].asString();
    if (code.find_first_not_of("0123456789") != std::string::npos)
    {
        error(callback, k400BadRequest, "invalid_verification");
        return;
    }
    accounts.handle(VerifyEmailCommand{body["email"].asString(), code, type.asString()},
                    respond(std::move(callback)));
}
