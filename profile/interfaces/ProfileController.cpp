#include "ProfileController.h"
#include "../../auth/application/AuthCommandService.h"
#include "../../auth/infrastructure/SupabaseIdentityProvider.h"
#include "../../shared/interfaces/HttpSupport.h"
#include "../application/PreferencesService.h"
#include "../application/ProfileServices.h"
#include "../infrastructure/ProfileJsonMapper.h"
#include "../infrastructure/SupabaseProfileRepository.h"
using namespace drogon;
namespace mirage::profile
{
namespace
{
const SupabaseProfileRepository repository;
const ProfileCommandService commands(repository);
const ProfileQueryService queries(repository);
const PreferencesCommandService preferenceCommands(repository);
const PreferencesQueryService preferenceQueries(repository);
const auth::SupabaseIdentityProvider provider;
const auth::AuthQueryService identities(provider);
using Callback = http::Callback;
using Authorized = std::function<void(ProfileAccess)>;
void authorize(const HttpRequestPtr &req, const std::string &target, Callback callback,
               Authorized done)
{
    std::string token;
    if (!http::bearer(req, token, callback))
        return;
    identities.handle(auth::GetCurrentUserQuery{token}, [target, token, callback,
                                                         done = std::move(done)](ApiResult result) {
        if (result.status != 200)
        {
            http::reply(callback, static_cast<HttpStatusCode>(result.status), result.body);
            return;
        }
        const auto id = result.body.get("id", "").asString();
        if (id.empty())
        {
            http::error(callback, k502BadGateway, "invalid_identity_response");
            return;
        }
        if (!target.empty() && target != id)
        {
            http::error(callback, k403Forbidden, "profile_access_denied");
            return;
        }
        done({id, token});
    });
}
ProfileCompletion respond(Callback callback, const char *section = "", bool created = false)
{
    return [callback, section = std::string(section), created](ProfileResult result) {
        if (!result.aggregate)
        {
            http::error(callback, static_cast<HttpStatusCode>(result.status), result.error.c_str());
            return;
        }
        auto json = ProfileJsonMapper::toJson(*result.aggregate);
        if (!section.empty())
            json = json[section];
        http::reply(callback, created ? k201Created : k200OK, json);
    };
}
void badPayload(const Callback &callback, const std::invalid_argument &error)
{
    http::error(callback, k400BadRequest, error.what());
}
} // namespace
void ProfileController::createProfile(const HttpRequestPtr &req, Callback &&callback)
{
    Json::Value body;
    if (!http::json(req, body, callback))
        return;
    authorize(req, "", callback, [body, callback](ProfileAccess access) {
        try
        {
            UserProfile p{drogon::utils::getUuid(),
                          access.userId,
                          ProfileJsonMapper::text(body, "displayName"),
                          ProfileJsonMapper::optionalText(body, "birthDate"),
                          ProfileJsonMapper::optionalText(body, "profileImageUrl"),
                          {},
                          "",
                          ""};
            commands.handle(CreateProfileCommand{access, std::move(p)},
                            respond(callback, "", true));
        }
        catch (const std::invalid_argument &e)
        {
            badPayload(callback, e);
        }
    });
}
void ProfileController::getProfile(const HttpRequestPtr &req, Callback &&callback,
                                   std::string userId)
{
    authorize(req, userId, callback, [callback](ProfileAccess access) {
        queries.handle(GetProfileQuery{access}, respond(callback));
    });
}
void ProfileController::updateProfile(const HttpRequestPtr &req, Callback &&callback,
                                      std::string userId)
{
    Json::Value body;
    if (!http::json(req, body, callback))
        return;
    authorize(req, userId, callback, [body, callback](ProfileAccess access) {
        try
        {
            commands.handle(
                UpdateProfileCommand{access, ProfileJsonMapper::text(body, "displayName"),
                                     ProfileJsonMapper::optionalText(body, "birthDate"),
                                     ProfileJsonMapper::optionalText(body, "profileImageUrl")},
                respond(callback));
        }
        catch (const std::invalid_argument &e)
        {
            badPayload(callback, e);
        }
    });
}
void ProfileController::getPreferences(const HttpRequestPtr &req, Callback &&callback,
                                       std::string userId)
{
    authorize(req, userId, callback, [callback](ProfileAccess access) {
        preferenceQueries.handle(GetProfileQuery{access}, respond(callback, "preferences"));
    });
}
void ProfileController::updatePreferences(const HttpRequestPtr &req, Callback &&callback,
                                          std::string userId)
{
    Json::Value body;
    if (!http::json(req, body, callback))
        return;
    authorize(req, userId, callback, [body, callback](ProfileAccess access) {
        try
        {
            preferenceCommands.handle(
                UpdatePreferencesCommand{access, ProfileJsonMapper::preferences(body)},
                respond(callback, "preferences"));
        }
        catch (const std::invalid_argument &e)
        {
            badPayload(callback, e);
        }
    });
}
void ProfileController::getMeasurements(const HttpRequestPtr &req, Callback &&callback,
                                        std::string userId)
{
    authorize(req, userId, callback, [callback](ProfileAccess access) {
        queries.handle(GetProfileQuery{access}, respond(callback, "measurements"));
    });
}
void ProfileController::updateMeasurements(const HttpRequestPtr &req, Callback &&callback,
                                           std::string userId)
{
    Json::Value body;
    if (!http::json(req, body, callback))
        return;
    authorize(req, userId, callback, [body, callback](ProfileAccess access) {
        try
        {
            commands.handle(
                RegisterMeasurementsCommand{access, ProfileJsonMapper::measurements(body)},
                respond(callback, "measurements"));
        }
        catch (const std::invalid_argument &e)
        {
            badPayload(callback, e);
        }
    });
}
} // namespace mirage::profile
