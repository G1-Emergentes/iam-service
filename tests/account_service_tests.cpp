#include "../auth/application/AccountService.h"
#include <iostream>
#include <stdexcept>
using namespace mirage;
using namespace mirage::auth;
using namespace mirage::profile;
void require(bool condition)
{
    if (!condition)
        throw std::runtime_error("Account service assertion failed");
}
const std::string userId = "22222222-2222-2222-2222-222222222222";
class Identity final : public IdentityProvider
{
  public:
    bool pending = false;
    int status = 200;
    std::string name = "Google Name";
    mutable int logouts = 0;
    void execute(IdentityOperation operation, Json::Value, std::string,
                 Completion done) const override
    {
        if (operation == IdentityOperation::Logout)
        {
            ++logouts;
            done({200, Json::Value(Json::objectValue)});
            return;
        }
        if (status != 200)
        {
            done(failure(status, "auth_request_rejected"));
            return;
        }
        Json::Value result;
        if (pending)
            result["id"] = userId;
        else
        {
            result["access_token"] = "access";
            result["refresh_token"] = "refresh";
            result["user"]["id"] = userId;
            result["user"]["user_metadata"]["full_name"] = name;
        }
        done({200, result});
    }
};
class Repository final : public ProfileRepository
{
  public:
    mutable std::optional<UserProfileAggregate> saved;
    mutable int reads = 0, creates = 0;
    bool unavailable = false, createFails = false, simulateRace = false;
    void findByUserId(const ProfileAccess &, ProfileCompletion done) const override
    {
        ++reads;
        if (unavailable)
        {
            done({503, {}, "storage_unavailable"});
            return;
        }
        done(saved ? ProfileResult{200, saved, ""} : ProfileResult{404, {}, "profile_not_found"});
    }
    void create(const ProfileAccess &, const UserProfileAggregate &profile,
                ProfileCompletion done) const override
    {
        ++creates;
        if (createFails)
        {
            done({503, {}, "storage_unavailable"});
            return;
        }
        saved = profile;
        done(simulateRace ? ProfileResult{409, {}, "profile_already_exists"}
                          : ProfileResult{200, saved, ""});
    }
    void updateProfile(const ProfileAccess &, const UserProfileAggregate &,
                       ProfileCompletion) const override
    {
        throw std::runtime_error("Unexpected update");
    }
    void updatePreferences(const ProfileAccess &, const StylePreferences &,
                           ProfileCompletion) const override
    {
        throw std::runtime_error("Unexpected preferences");
    }
    void saveMeasurements(const ProfileAccess &, const BodyMeasurements &,
                          ProfileCompletion) const override
    {
        throw std::runtime_error("Unexpected measurements");
    }
};
int main()
{
    Identity identity;
    Repository repository;
    AuthCommandService authentication(identity);
    ProfileCommandService profiles(repository);
    ProfileQueryService queries(repository);
    AccountService accounts(authentication, profiles, queries,
                            [] { return "11111111-1111-1111-1111-111111111111"; });
    int callbacks = 0;
    auto success = [&](ApiResult result) {
        ++callbacks;
        require(result.status == 200);
        require(result.body["profile_ready"].asBool());
    };
    identity.pending = true;
    accounts.handle(RegisterUserCommand{"Ana", "user@example.com", "password"},
                    [&](ApiResult result) {
                        ++callbacks;
                        require(result.status == 200);
                        require(!result.body["profile_ready"].asBool());
                    });
    require(repository.reads == 0 && repository.creates == 0);
    identity.pending = false;
    accounts.handle(GoogleSignInCommand{"google-token", ""}, success);
    require(repository.creates == 1 && repository.saved->profile().displayName == "Google Name");
    repository.saved->registerMeasurements({175, 45, 95, 80, 96});
    identity.name = "Different Name";
    accounts.handle(LoginCommand{"user@example.com", "password"}, success);
    require(repository.creates == 1 && repository.saved->profile().displayName == "Google Name");
    require(repository.saved->measurements()->height == 175);
    repository.saved.reset();
    repository.simulateRace = true;
    accounts.handle(LoginCommand{"user@example.com", "password"}, success);
    require(repository.creates == 2);
    repository.simulateRace = false;
    repository.saved.reset();
    repository.createFails = true;
    accounts.handle(LoginCommand{"user@example.com", "password"}, [&](ApiResult result) {
        ++callbacks;
        require(result.status == 503);
        require(!result.body.isMember("access_token"));
    });
    require(identity.logouts == 1);
    repository.createFails = false;
    repository.unavailable = true;
    accounts.handle(LoginCommand{"user@example.com", "password"}, [&](ApiResult result) {
        ++callbacks;
        require(result.status == 503);
    });
    require(identity.logouts == 2);
    const int reads = repository.reads;
    identity.status = 401;
    accounts.handle(LoginCommand{"user@example.com", "bad"}, [&](ApiResult result) {
        ++callbacks;
        require(result.status == 401);
    });
    require(repository.reads == reads && callbacks == 7);
    std::cout << "PASS: pending signup, Google profile provisioning, idempotent login, conflict "
                 "recovery, compensation, credential rejection\n";
}
