#include "SupabaseProfileRepository.h"
#include "../../shared/infrastructure/SupabaseClient.h"
#include "ProfileJsonMapper.h"
namespace mirage::profile
{
namespace
{
void rpc(const char *name, const ProfileAccess &access, Json::Value parameters,
         ProfileCompletion done)
{
    SupabaseClient::request(
        drogon::Post, std::string("/rest/v1/rpc/") + name, parameters, access.bearer,
        [done = std::move(done), expectedUser = access.userId](ApiResult result) {
            if (result.status >= 400)
            {
                const auto code = result.body.get("code", "").asString();
                if (code == "PGRST202" || code == "42P01")
                {
                    done({503, {}, "profile_schema_not_installed"});
                    return;
                }
                if (code == "23505")
                {
                    done({409, {}, "profile_already_exists"});
                    return;
                }
                if (code == "P0002")
                {
                    done({404, {}, "profile_not_found"});
                    return;
                }
                const int status = result.status == 401 || result.status == 403 ? 403
                                   : result.status >= 500                       ? 502
                                                                                : 400;
                done({status,
                      {},
                      status == 403 ? "profile_access_denied" : "profile_storage_failed"});
                return;
            }
            if (result.body.isNull())
            {
                done({404, {}, "profile_not_found"});
                return;
            }
            try
            {
                auto aggregate = ProfileJsonMapper::fromJson(result.body);
                if (!aggregate.belongsTo(expectedUser))
                {
                    done({403, {}, "profile_access_denied"});
                    return;
                }
                done({200, std::move(aggregate), ""});
            }
            catch (const std::exception &)
            {
                done({502, {}, "invalid_profile_storage_response"});
            }
        });
}
} // namespace
void SupabaseProfileRepository::findByUserId(const ProfileAccess &access,
                                             ProfileCompletion done) const
{
    rpc("mirage_get_profile", access, Json::Value(Json::objectValue), std::move(done));
}
void SupabaseProfileRepository::create(const ProfileAccess &access,
                                       const UserProfileAggregate &profile,
                                       ProfileCompletion done) const
{
    Json::Value p;
    p["p_profile"] = ProfileJsonMapper::toJson(profile);
    rpc("mirage_create_profile", access, p, std::move(done));
}
void SupabaseProfileRepository::updateProfile(const ProfileAccess &access,
                                              const UserProfileAggregate &profile,
                                              ProfileCompletion done) const
{
    Json::Value p;
    p["p_profile"] = ProfileJsonMapper::toJson(profile);
    rpc("mirage_update_profile", access, p, std::move(done));
}
void SupabaseProfileRepository::updatePreferences(const ProfileAccess &access,
                                                  const StylePreferences &preferences,
                                                  ProfileCompletion done) const
{
    Json::Value p;
    p["p_preferences"] = ProfileJsonMapper::toJson(preferences);
    rpc("mirage_set_preferences", access, p, std::move(done));
}
void SupabaseProfileRepository::saveMeasurements(const ProfileAccess &access,
                                                 const BodyMeasurements &measurements,
                                                 ProfileCompletion done) const
{
    Json::Value p;
    p["p_measurements"] = ProfileJsonMapper::toJson(measurements);
    rpc("mirage_set_measurements", access, p, std::move(done));
}
} // namespace mirage::profile
