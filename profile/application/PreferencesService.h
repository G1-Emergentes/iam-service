#pragma once
#include "ProfileCommands.h"
namespace mirage::profile
{
class PreferencesCommandService
{
    const ProfileRepository &repository_;

  public:
    explicit PreferencesCommandService(const ProfileRepository &repository)
        : repository_(repository)
    {
    }
    void handle(const UpdatePreferencesCommand &, ProfileCompletion) const;
};
class PreferencesQueryService
{
    const ProfileRepository &repository_;

  public:
    explicit PreferencesQueryService(const ProfileRepository &repository) : repository_(repository)
    {
    }
    void handle(const GetProfileQuery &query, ProfileCompletion done) const
    {
        repository_.findByUserId(query.access, std::move(done));
    }
};
} // namespace mirage::profile
