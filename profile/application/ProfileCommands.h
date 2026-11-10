#pragma once
#include "../domain/repositories/ProfileRepository.h"
namespace mirage::profile
{
struct CreateProfileCommand
{
    ProfileAccess access;
    UserProfile profile;
};
struct UpdateProfileCommand
{
    ProfileAccess access;
    std::string displayName;
    std::optional<std::string> birthDate, profileImageUrl;
};
struct UpdatePreferencesCommand
{
    ProfileAccess access;
    StylePreferences preferences;
};
struct RegisterMeasurementsCommand
{
    ProfileAccess access;
    BodyMeasurements measurements;
};
struct GetProfileQuery
{
    ProfileAccess access;
};
} // namespace mirage::profile
