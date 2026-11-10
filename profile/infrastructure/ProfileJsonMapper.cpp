#include "ProfileJsonMapper.h"
namespace mirage::profile
{
std::string ProfileJsonMapper::text(const Json::Value &json, const char *name)
{
    if (!json.isObject() || !json[name].isString())
        throw std::invalid_argument("invalid_profile_payload");
    return json[name].asString();
}
std::optional<std::string> ProfileJsonMapper::optionalText(const Json::Value &json,
                                                           const char *name)
{
    if (!json.isMember(name) || json[name].isNull())
        return {};
    return text(json, name);
}
StylePreferences ProfileJsonMapper::preferences(const Json::Value &json)
{
    if (!json.isObject())
        throw std::invalid_argument("preferences_must_be_an_object");
    auto list = [&](const char *name) {
        const auto &values = json[name];
        if (!values.isArray() || values.size() > 50)
            throw std::invalid_argument("invalid_preferences_list");
        std::vector<std::string> result;
        for (const auto &value : values)
        {
            if (!value.isString())
                throw std::invalid_argument("invalid_preference_value");
            result.push_back(value.asString());
        }
        return result;
    };
    return {list("preferredStyles"), list("preferredColors"), list("avoidedColors"),
            list("preferredCategories")};
}
BodyMeasurements ProfileJsonMapper::measurements(const Json::Value &json)
{
    if (!json.isObject())
        throw std::invalid_argument("measurements_must_be_an_object");
    auto number = [&](const char *name) {
        if (!json[name].isNumeric() || json[name].isBool())
            throw std::invalid_argument("measurement_must_be_numeric");
        return json[name].asDouble();
    };
    return {number("height"), number("shoulderWidth"), number("chest"), number("waist"),
            number("hip")};
}
Json::Value ProfileJsonMapper::toJson(const UserProfileAggregate &aggregate)
{
    const auto &profile = aggregate.profile();
    Json::Value json;
    json["id"] = profile.id;
    json["userId"] = profile.userId;
    json["displayName"] = profile.displayName;
    json["birthDate"] = profile.birthDate ? Json::Value(*profile.birthDate) : Json::Value();
    json["profileImageUrl"] =
        profile.profileImageUrl ? Json::Value(*profile.profileImageUrl) : Json::Value();
    json["avatarReference"] =
        profile.avatarReference ? Json::Value(*profile.avatarReference) : Json::Value();
    json["createdAt"] = profile.createdAt;
    json["updatedAt"] = profile.updatedAt;
    json["preferences"] = toJson(aggregate.preferences());
    json["measurements"] =
        aggregate.measurements() ? toJson(*aggregate.measurements()) : Json::Value();

    return json;
}
Json::Value ProfileJsonMapper::toJson(const StylePreferences &p)
{
    auto array = [](const std::vector<std::string> &values) {
        Json::Value json(Json::arrayValue);
        for (const auto &value : values)
            json.append(value);
        return json;
    };
    Json::Value json;
    json["preferredStyles"] = array(p.preferredStyles);
    json["preferredColors"] = array(p.preferredColors);
    json["avoidedColors"] = array(p.avoidedColors);
    json["preferredCategories"] = array(p.preferredCategories);
    return json;
}
Json::Value ProfileJsonMapper::toJson(const BodyMeasurements &m)
{
    Json::Value json;
    json["height"] = m.height;
    json["shoulderWidth"] = m.shoulderWidth;
    json["chest"] = m.chest;
    json["waist"] = m.waist;
    json["hip"] = m.hip;
    return json;
}
UserProfileAggregate ProfileJsonMapper::fromJson(const Json::Value &json)
{
    UserProfile profile{text(json, "id"),
                        text(json, "userId"),
                        text(json, "displayName"),
                        optionalText(json, "birthDate"),
                        optionalText(json, "profileImageUrl"),
                        optionalText(json, "avatarReference"),
                        text(json, "createdAt"),
                        text(json, "updatedAt")};
    std::optional<BodyMeasurements> body;
    if (!json["measurements"].isNull())
        body = measurements(json["measurements"]);
    return UserProfileAggregate(std::move(profile), preferences(json["preferences"]), body);
}
} // namespace mirage::profile
