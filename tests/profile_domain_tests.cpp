#include "../profile/application/PreferencesService.h"
#include "../profile/application/ProfileServices.h"
#include <iostream>
#include <limits>
using namespace mirage::profile;
void require(bool condition)
{
    if (!condition)
        throw std::runtime_error("Test failed");
}
template <class Action> void rejects(Action action)
{
    bool rejected = false;
    try
    {
        action();
    }
    catch (const std::invalid_argument &)
    {
        rejected = true;
    }
    require(rejected);
}
class Repository final : public ProfileRepository
{
  public:
    mutable std::optional<UserProfileAggregate> saved;
    void findByUserId(const ProfileAccess &, ProfileCompletion done) const override
    {
        done(saved ? ProfileResult{200, saved, ""} : ProfileResult{404, {}, "profile_not_found"});
    }
    void create(const ProfileAccess &, const UserProfileAggregate &profile,
                ProfileCompletion done) const override
    {
        saved = profile;
        done({200, saved, ""});
    }
    void updateProfile(const ProfileAccess &, const UserProfileAggregate &profile,
                       ProfileCompletion done) const override
    {
        saved = profile;
        done({200, saved, ""});
    }
    void updatePreferences(const ProfileAccess &, const StylePreferences &preferences,
                           ProfileCompletion done) const override
    {
        saved->updatePreferences(preferences);
        done({200, saved, ""});
    }
    void saveMeasurements(const ProfileAccess &, const BodyMeasurements &body,
                          ProfileCompletion done) const override
    {
        saved->registerMeasurements(body);
        done({200, saved, ""});
    }
};
int main()
{
    UserProfile profile{"11111111-1111-1111-1111-111111111111",
                        "22222222-2222-2222-2222-222222222222",
                        "Mateo",
                        {},
                        {},
                        {},
                        "",
                        ""};
    UserProfileAggregate aggregate(profile);
    require(aggregate.belongsTo(profile.userId));
    require(!aggregate.measurements());
    aggregate.registerMeasurements({175, 45, 95, 80, 96});
    require(aggregate.measurements()->height == 175);
    rejects([&] { aggregate.registerMeasurements({-1, 45, 95, 80, 96}); });
    rejects([&] {
        aggregate.registerMeasurements({std::numeric_limits<double>::quiet_NaN(), 45, 95, 80, 96});
    });
    require(aggregate.measurements()->height == 175);
    rejects([&] { aggregate.updatePreferences({{"casual", "casual"}, {}, {}, {}}); });
    rejects([&] { aggregate.updatePreferences({{}, {"blue"}, {"blue"}, {}}); });
    rejects([&] { aggregate.updateProfile("Mateo", "2023-02-29", {}); });
    rejects([&] { aggregate.updateProfile("Mateo", "2999-01-01", {}); });
    rejects([&] { aggregate.updateProfile("Mateo", {}, "http://example.com/avatar"); });
    aggregate.updateProfile("Mateo", "2000-02-29", {});
    Repository repository;
    ProfileCommandService commands(repository);
    ProfileQueryService queries(repository);
    PreferencesCommandService preferenceCommands(repository);
    ProfileAccess access{profile.userId, "Bearer test"};
    commands.handle(CreateProfileCommand{access, profile},
                    [](ProfileResult result) { require(result.status == 200); });
    commands.handle(
        RegisterMeasurementsCommand{access, {180, 48, 100, 85, 100}},
        [](ProfileResult result) { require(result.aggregate->measurements()->height == 180); });
    preferenceCommands.handle(
        UpdatePreferencesCommand{access, {{"casual"}, {}, {}, {}}}, [](ProfileResult result) {
            require(result.aggregate->preferences().preferredStyles[0] == "casual");
        });
    commands.handle(RegisterMeasurementsCommand{access, {0, 48, 100, 85, 100}},
                    [](ProfileResult result) { require(result.status == 400); });
    require(repository.saved->measurements()->height == 180);
    auto other = access;
    other.userId = "33333333-3333-3333-3333-333333333333";
    commands.handle(CreateProfileCommand{other, profile},
                    [](ProfileResult result) { require(result.status == 403); });
    queries.handle(GetProfileQuery{access},
                   [](ProfileResult result) { require(result.aggregate.has_value()); });
    std::cout << "PASS: aggregate invariants, measurements, dates, ownership, CQRS handlers\n";
}
