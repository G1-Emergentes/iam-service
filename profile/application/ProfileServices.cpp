#include "ProfileServices.h"
namespace mirage::profile
{
void ProfileCommandService::handle(const CreateProfileCommand &command,
                                   ProfileCompletion done) const
{
    if (command.profile.userId != command.access.userId)
    {
        done({403, {}, "profile_owner_mismatch"});
        return;
    }
    try
    {
        UserProfileAggregate aggregate(command.profile);
        repository_.create(command.access, aggregate, std::move(done));
    }
    catch (const std::invalid_argument &e)
    {
        done({400, {}, e.what()});
    }
}
void ProfileCommandService::handle(const UpdateProfileCommand &command,
                                   ProfileCompletion done) const
{
    repository_.findByUserId(
        command.access, [this, command, done = std::move(done)](ProfileResult result) {
            if (!result.aggregate)
            {
                done(std::move(result));
                return;
            }
            try
            {
                result.aggregate->updateProfile(command.displayName, command.birthDate,
                                                command.profileImageUrl);
            }
            catch (const std::invalid_argument &e)
            {
                done({400, {}, e.what()});
                return;
            }
            repository_.updateProfile(command.access, *result.aggregate, std::move(done));
        });
}
void ProfileCommandService::handle(const RegisterMeasurementsCommand &command,
                                   ProfileCompletion done) const
{
    repository_.findByUserId(
        command.access, [this, command, done = std::move(done)](ProfileResult result) {
            if (!result.aggregate)
            {
                done(std::move(result));
                return;
            }
            try
            {
                result.aggregate->registerMeasurements(command.measurements);
            }
            catch (const std::invalid_argument &e)
            {
                done({400, {}, e.what()});
                return;
            }
            repository_.saveMeasurements(command.access, *result.aggregate->measurements(),
                                         std::move(done));
        });
}
} // namespace mirage::profile
