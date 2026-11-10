#pragma once
#include <drogon/HttpController.h>
namespace mirage::profile
{
class ProfileController : public drogon::HttpController<ProfileController>
{
  public:
    METHOD_LIST_BEGIN
    ADD_METHOD_TO(ProfileController::createProfile, "/api/v1/profiles", drogon::Post);
    ADD_METHOD_TO(ProfileController::getProfile, "/api/v1/profiles/{1}", drogon::Get);
    ADD_METHOD_TO(ProfileController::updateProfile, "/api/v1/profiles/{1}", drogon::Put);
    ADD_METHOD_TO(ProfileController::getPreferences, "/api/v1/profiles/{1}/preferences",
                  drogon::Get);
    ADD_METHOD_TO(ProfileController::updatePreferences, "/api/v1/profiles/{1}/preferences",
                  drogon::Put);
    ADD_METHOD_TO(ProfileController::getMeasurements, "/api/v1/profiles/{1}/measurements",
                  drogon::Get);
    ADD_METHOD_TO(ProfileController::updateMeasurements, "/api/v1/profiles/{1}/measurements",
                  drogon::Put);
    METHOD_LIST_END
    using Callback = std::function<void(const drogon::HttpResponsePtr &)>;
    void createProfile(const drogon::HttpRequestPtr &, Callback &&);
    void getProfile(const drogon::HttpRequestPtr &, Callback &&, std::string userId);
    void updateProfile(const drogon::HttpRequestPtr &, Callback &&, std::string userId);
    void getPreferences(const drogon::HttpRequestPtr &, Callback &&, std::string userId);
    void updatePreferences(const drogon::HttpRequestPtr &, Callback &&, std::string userId);
    void getMeasurements(const drogon::HttpRequestPtr &, Callback &&, std::string userId);
    void updateMeasurements(const drogon::HttpRequestPtr &, Callback &&, std::string userId);
};
} // namespace mirage::profile
