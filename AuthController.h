#pragma once
#include <drogon/HttpController.h>

using namespace drogon;

class AuthController : public HttpController<AuthController>
{
  public:
    METHOD_LIST_BEGIN
    ADD_METHOD_TO(AuthController::registerUser, "/api/v1/auth/register", Post);
    ADD_METHOD_TO(AuthController::login, "/api/v1/auth/login", Post);
    ADD_METHOD_TO(AuthController::google, "/api/v1/auth/google", Post);
    ADD_METHOD_TO(AuthController::refresh, "/api/v1/auth/refresh", Post);
    ADD_METHOD_TO(AuthController::me, "/api/v1/auth/me", Get);
    ADD_METHOD_TO(AuthController::logout, "/api/v1/auth/logout", Post);
    ADD_METHOD_TO(AuthController::forgotPassword, "/api/v1/auth/forgot-password", Post);
    ADD_METHOD_TO(AuthController::resetPassword, "/api/v1/auth/reset-password", Put);
    ADD_METHOD_TO(AuthController::resendVerification, "/api/v1/auth/resend-verification", Post);
    ADD_METHOD_TO(AuthController::verifyEmail, "/api/v1/auth/verify-email", Post);
    METHOD_LIST_END

    void registerUser(const HttpRequestPtr &req,
                      std::function<void(const HttpResponsePtr &)> &&callback);

    void login(const HttpRequestPtr &req, std::function<void(const HttpResponsePtr &)> &&callback);
    void google(const HttpRequestPtr &, std::function<void(const HttpResponsePtr &)> &&);
    void refresh(const HttpRequestPtr &, std::function<void(const HttpResponsePtr &)> &&);
    void me(const HttpRequestPtr &, std::function<void(const HttpResponsePtr &)> &&);
    void logout(const HttpRequestPtr &, std::function<void(const HttpResponsePtr &)> &&);
    void forgotPassword(const HttpRequestPtr &, std::function<void(const HttpResponsePtr &)> &&);
    void resendVerification(const HttpRequestPtr &,
                            std::function<void(const HttpResponsePtr &)> &&);
    void verifyEmail(const HttpRequestPtr &, std::function<void(const HttpResponsePtr &)> &&);
    void resetPassword(const HttpRequestPtr &, std::function<void(const HttpResponsePtr &)> &&);
};
