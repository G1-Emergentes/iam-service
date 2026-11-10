#pragma once
#include "ProfileCommands.h"
namespace mirage::profile
{
class ProfileCommandService
{
    const ProfileRepository &repository_;

  public:
    explicit ProfileCommandService(const ProfileRepository &repository) : repository_(repository) {}
    void handle(const CreateProfileCommand &, ProfileCompletion) const;
    void handle(const UpdateProfileCommand &, ProfileCompletion) const;
    void handle(const RegisterMeasurementsCommand &, ProfileCompletion) const;
};
class ProfileQueryService
{
    const ProfileRepository &repository_;

  public:
    explicit ProfileQueryService(const ProfileRepository &repository) : repository_(repository) {}
    void handle(const GetProfileQuery &query, ProfileCompletion done) const
    {
        repository_.findByUserId(query.access, std::move(done));
    }
};
} // namespace mirage::profile
